/* Request ownership for retained archives. No generation or implicit retry API. */
(function (root) {
  'use strict';
  const hash = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
  const copy = value => JSON.parse(JSON.stringify(value));
  class ReviewSession {
    constructor(request) {
      this.request = request; this.epoch = 0; this.current = null;
      this.reportTicket = 0; this.reviewTicket = 0; this.reportValue = null;
      this.pending = new Map(); this.unconfirmed = new Map();
    }
    async open(key) {
      const epoch = ++this.epoch, recovery = this.unconfirmed.get(key);
      this.current = null; this.reportValue = null; ++this.reportTicket; ++this.reviewTicket;
      try {
        const snapshot = await this.request('/archive', {key});
        if (epoch !== this.epoch) return null;
        const a = snapshot.archive;
        if (!a || !hash(snapshot.archive_sha256) || a.chapters_sha256 !== snapshot.archive_sha256
            || !hash(snapshot.playback_sha256) || !Array.isArray(a.segments) || !Array.isArray(a.chapters)
            || a.sample_rate !== 48000 || !Number.isSafeInteger(a.master?.samples) || a.master.samples < 1
            || !this.bound(a, snapshot.playback)) throw Error('Invalid archive inspection identity');
        this.current = {key, snapshot};
        // A read begun before a failed/in-flight write cannot clear that uncertainty.
        if (!this.pending.has(key) && this.unconfirmed.get(key) === recovery) this.unconfirmed.delete(key);
        return this.current;
      } catch (error) { if (epoch !== this.epoch) return null; throw error; }
    }
    bound(archive, value) {
      return value && value.manifest_sha256 === archive.manifest_sha256 && value.master_sha256 === archive.master.sha256;
    }
    requireCurrent() { if (!this.current) throw Error('Inspect an archive first'); return this.current; }
    blocked() { return !this.current || this.pending.has(this.current.key) || this.unconfirmed.has(this.current.key); }
    async readRecord(route, identifier, ticketName, hashName) {
      const selected = this.requireCurrent(), epoch = this.epoch, ticket = ++this[ticketName];
      if (route === '/report') this.reportValue = null;
      try {
        const value = await this.request(route, {key:selected.key, archive_sha256:selected.snapshot.archive_sha256, id:identifier});
        if (epoch !== this.epoch || ticket !== this[ticketName]) return null;
        if (value[hashName] !== identifier || !this.bound(selected.snapshot.archive, value.archive)) throw Error('Record identity differs from this archive');
        if (route === '/report') this.reportValue = value;
        return value;
      } catch (error) { if (epoch !== this.epoch || ticket !== this[ticketName]) return null; throw error; }
    }
    report(id) { return this.readRecord('/report', id, 'reportTicket', 'report_sha256'); }
    savedReview(id) { return this.readRecord('/review', id, 'reviewTicket', 'review_sha256'); }
    async write(route, value) {
      const selected = this.requireCurrent(), epoch = this.epoch, key = selected.key;
      if (this.pending.has(key)) throw Error('A save is already in progress for this archive');
      if (this.unconfirmed.has(key)) throw Error('Inspect this archive before another save; the previous outcome is unconfirmed');
      const body = copy(value); body.archive_sha256 = selected.snapshot.archive_sha256;
      if (route === '/bookmark') body.expected_playback_sha256 = selected.snapshot.playback_sha256;
      const token = {}; this.pending.set(key, token);
      try {
        const result = await this.request(route, {key}, body);
        if (route === '/bookmark') {
          if (!hash(result.playback_sha256) || !this.bound(selected.snapshot.archive, result.playback)
              || result.playback.sample !== body.sample || result.playback.rate !== body.rate
              || JSON.stringify(result.playback.loop) !== JSON.stringify(body.loop)) throw Error('Bookmark acknowledgement identity differs');
        } else if (!hash(result.id) || typeof result.reused !== 'boolean') throw Error('Invalid review acknowledgement');
        const current = this.epoch === epoch;
        if (current && route === '/bookmark') {
          selected.snapshot.playback = result.playback; selected.snapshot.playback_sha256 = result.playback_sha256;
        } else if (current && !selected.snapshot.reviews.includes(result.id)) selected.snapshot.reviews.push(result.id);
        return {key, current, result};
      } catch (error) {
        this.unconfirmed.set(key, token);
        throw Error(`${key}: ${error.message}. Inspect this archive before saving again; no retry was sent.`);
      } finally { if (this.pending.get(key) === token) this.pending.delete(key); }
    }
    bookmark(value) { return this.write('/bookmark', value); }
    review(value) { return this.write('/review', value); }
  }
  const api = {ReviewSession};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SpokenReview = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
