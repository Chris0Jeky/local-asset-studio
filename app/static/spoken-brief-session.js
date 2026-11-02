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
      this.current = null; this.clearReport(); this.clearReview();
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
    clearReport() { ++this.reportTicket; this.reportValue = null; }
    clearReview() { ++this.reviewTicket; }
    report(id) { return this.readRecord('/report', id, 'reportTicket', 'report_sha256'); }
    savedReview(id) { return this.readRecord('/review', id, 'reviewTicket', 'review_sha256'); }
    async write(route, value) {
      const selected = this.requireCurrent(), epoch = this.epoch, key = selected.key;
      if (this.pending.has(key)) throw Error('A save is already in progress for this archive');
      if (this.unconfirmed.has(key)) throw Error('Inspect this archive before another save; the displayed state may precede an earlier save');
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
        // An overlapping inspection may have read before this successful commit.
        // Only a new inspection begun after completion can restore write authority.
        if (!current) this.unconfirmed.set(key, token);
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
  class SourcePreviewSession {
    constructor(request) { this.request = request; this.root = null; this.epoch = 0; this.rootTicket = 0; }
    invalidate() { ++this.epoch; }
    async refresh() {
      const ticket = ++this.rootTicket;
      this.root = null; this.invalidate();
      try {
        const value = await this.request('/capabilities');
        if (ticket !== this.rootTicket) return null;
        if (value.enabled && !hash(value.source_root_id)) throw Error('Invalid source root identity');
        this.root = value.enabled ? value.source_root_id : null;
        return value;
      } catch (error) { if (ticket !== this.rootTicket) return null; throw error; }
    }
    async preview(key) {
      const epoch = ++this.epoch, root = this.root;
      if (!root) throw Error('Refresh source access before previewing');
      try {
        const value = await this.request('/source-preview', {key, root_id:root});
        if (epoch !== this.epoch || root !== this.root) return null;
        if (value.root_id !== root || !hash(value.manifest?.source?.sha256)
            || !Array.isArray(value.manifest?.segments) || !value.manifest?.omissions
            || typeof value.manifest.omissions !== 'object' || Array.isArray(value.manifest.omissions)
            || !Number.isSafeInteger(value.batch_count) || value.batch_count < 1
            || value.generation_submitted !== false) throw Error('Invalid source preview identity');
        return value;
      } catch (error) { if (epoch !== this.epoch || root !== this.root) return null; throw error; }
    }
  }
  class NarrationSession {
    constructor(request) { this.request=request; this.epoch=0; this.ticket=0; this.current=null; this.attempted=new Set(); this.pending=new Set(); }
    select(key, root, manifest=null) { ++this.epoch; ++this.ticket; this.current=key ? {key,root_id:root,manifest_sha256:manifest,value:null} : null; }
    async refresh() {
      const selected=this.current, epoch=this.epoch, ticket=++this.ticket;
      if (!selected || !hash(selected.root_id)) throw Error('Select a retained narration first');
      try {
        const value=await this.request('/narration',{key:selected.key,root_id:selected.root_id});
        if (epoch!==this.epoch || ticket!==this.ticket) return null;
        if (value.key!==selected.key || value.root_id!==selected.root_id || !hash(value.manifest_sha256)
            || (selected.manifest_sha256 && value.manifest_sha256!==selected.manifest_sha256)) throw Error('Narration identity differs from the selection');
        selected.manifest_sha256=value.manifest_sha256; selected.value=value;
        return value;
      } catch(error) { if(epoch!==this.epoch || ticket!==this.ticket) return null; throw error; }
    }
    async start(key, preview) {
      if (!hash(preview?.root_id) || !hash(preview?.preview_sha256) || !hash(preview?.manifest?.manifest_sha256)
          || typeof preview.run_key!=='string' || !preview.run_key) throw Error('Preview this source before Start');
      const id=preview.root_id+':'+preview.run_key;
      if(this.attempted.has(id)) {
        if(this.current?.key!==preview.run_key || this.current?.root_id!==preview.root_id)
          this.select(preview.run_key,preview.root_id,preview.manifest.manifest_sha256);
        throw Error('Start was already requested. Refresh retained progress; no retry was sent.');
      }
      this.select(preview.run_key,preview.root_id,preview.manifest.manifest_sha256); this.attempted.add(id);
      return this.write('/narration/start',{key,root_id:preview.root_id,manifest_sha256:preview.manifest.manifest_sha256,preview_sha256:preview.preview_sha256});
    }
    async recover() {
      const selected=this.current;
      if(!selected || !hash(selected.manifest_sha256)) throw Error('Refresh retained progress before recovery');
      return this.write('/narration/recover',{key:selected.key,root_id:selected.root_id,manifest_sha256:selected.manifest_sha256});
    }
    async write(route, body) {
      const selected=this.current, epoch=this.epoch, id=selected.root_id+':'+selected.key;
      if(this.pending.has(id)) throw Error('This narration request is still pending');
      this.pending.add(id); ++this.ticket;
      try {
        const value=await this.request(route,{},body);
        if(epoch!==this.epoch) return null;
        if(value.key!==selected.key || value.root_id!==selected.root_id || value.manifest_sha256!==selected.manifest_sha256) throw Error('Narration acknowledgement identity differs');
        return value;
      } catch(error) {
        if(epoch!==this.epoch) return null;
        throw Error(`${error.message}. Refresh retained progress; no create or Start was retried.`);
      } finally { this.pending.delete(id); }
    }
  }
  const api = {ReviewSession, SourcePreviewSession, NarrationSession};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SpokenReview = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
