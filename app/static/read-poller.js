/* Bounded polling for independent read lanes. A lane schedules only after its
 * prior read settles, and an explicit refresh coalesces behind an active read.
 */
(function(global){
  'use strict';
  class ReadPoller {
    constructor(options={}) {
      this.document=options.document||global.document;
      this.setTimeout=options.setTimeout||global.setTimeout.bind(global);
      this.clearTimeout=options.clearTimeout||global.clearTimeout.bind(global);
      this.lanes=new Map();this.started=false;this.disposed=false;
      this.visible=()=>{if(!this.document.hidden)this.wake(true);};
      this.document?.addEventListener?.('visibilitychange',this.visible);
    }
    register(name, options) {
      if(this.lanes.has(name))throw Error('Read lane already registered: '+name);
      const lane={name,task:options.task,interval:options.interval,shouldPoll:options.shouldPoll||(()=>true),timer:null,inFlight:null,queued:null};
      this.lanes.set(name,lane);if(this.started)this._schedule(lane);return this;
    }
    start() { if(this.disposed)return;this.started=true;this.wake(); }
    wake(immediate=false) { if(this.disposed||!this.started||this.document?.hidden)return;for(const lane of this.lanes.values()){if(immediate&&lane.shouldPoll()){if(lane.timer!==null){this.clearTimeout(lane.timer);lane.timer=null;}this._run(lane,[]);}else this._schedule(lane);} }
    refresh(name, ...args) {
      const lane=this.lanes.get(name);if(!lane||this.disposed)return Promise.resolve();
      if(lane.timer!==null){this.clearTimeout(lane.timer);lane.timer=null;}
      if(lane.inFlight){
        if(!lane.queued){let resolve;lane.queued={args,promise:new Promise(done=>{resolve=done;}),resolve};}
        else lane.queued.args=args;
        return lane.queued.promise;
      }
      return this._run(lane,args);
    }
    dispose() {
      if(this.disposed)return;this.disposed=true;this.document?.removeEventListener?.('visibilitychange',this.visible);
      for(const lane of this.lanes.values()){if(lane.timer!==null)this.clearTimeout(lane.timer);lane.timer=null;lane.queued?.resolve();lane.queued=null;}
    }
    _schedule(lane) {
      if(lane.timer!==null){this.clearTimeout(lane.timer);lane.timer=null;}
      if(!this.started||this.disposed||this.document?.hidden||!lane.shouldPoll())return;
      const delay=Math.max(0,Number(typeof lane.interval==='function'?lane.interval():lane.interval)||0);
      lane.timer=this.setTimeout(()=>{lane.timer=null;if(!this.document?.hidden&&lane.shouldPoll())this._run(lane,[]);},delay);
    }
    _run(lane,args) {
      if(lane.inFlight)return lane.inFlight;
      lane.inFlight=Promise.resolve().then(()=>lane.task(...args)).catch(()=>undefined).then(result=>{
        lane.inFlight=null;const queued=lane.queued;lane.queued=null;
        if(queued){this._run(lane,queued.args).then(queued.resolve);}
        else this._schedule(lane);
        return result;
      });
      return lane.inFlight;
    }
  }
  global.ReadPoller=ReadPoller;
})(window);
