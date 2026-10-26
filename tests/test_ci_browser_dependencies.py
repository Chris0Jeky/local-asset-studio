"""Execute the CI installer with controlled commands; never install local packages."""
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts' / 'ci-install-chromium.sh'
try: RELEASE = platform.freedesktop_os_release()
except OSError: RELEASE = {}
SUPPORTED = (sys.platform.startswith('linux') and RELEASE.get('ID') == 'ubuntu'
             and RELEASE.get('VERSION_ID') == '24.04' and shutil.which('bash')
             and Path('/usr/bin/apt-get').exists() and Path('/usr/bin/apt-config').exists())

COMMON = '''import json, os, pathlib, shlex, subprocess, sys
def record(value):
    with open(os.environ['CI_BROWSER_PROBE_LOG'], 'a') as stream:
        stream.write(json.dumps(value)+'\\n')
'''
SUDO = COMMON + '''args=sys.argv[1:]
record({'kind':'sudo','args':args})
assert args[0]=='-n', args
# Model sudo's environment reset: APT_CONFIG is deliberately not preserved.
environment={key:value for key,value in os.environ.items() if key.startswith('CI_BROWSER_PROBE_') or key=='PATH'}
environment['CI_BROWSER_PROBE_SUDO']='1'
os.execvpe(args[1],args[1:],environment)
'''
TIMEOUT = COMMON + '''args=sys.argv[1:]
record({'kind':'timeout','args':args,'elevated':os.environ.get('CI_BROWSER_PROBE_SUDO')=='1'})
assert args[0].startswith('--kill-after='), args
assert args[1].endswith('s') and 0<int(args[1][:-1])<=180, args
if os.environ.get('CI_BROWSER_PROBE_FAILURE')=='timeout-deps' and os.environ.get('CI_BROWSER_PROBE_SUDO')=='1':
    raise SystemExit(124)
os.execvpe(args[2],args[2:],os.environ)
'''
PYTHON = COMMON + '''args=sys.argv[1:]
assert args[:2]==['-m','playwright'] and args[-1]=='chromium', args
phase=args[2]
event={'kind':'playwright','phase':phase,'elevated':os.environ.get('CI_BROWSER_PROBE_SUDO')=='1'}
if phase=='install-deps':
    config=pathlib.Path(os.environ['APT_CONFIG'])
    event['apt_config']=str(config)
    event['config']=config.read_text()
    dumped=subprocess.run(['/usr/bin/apt-config','dump'],check=True,capture_output=True,text=True,timeout=5).stdout
    effective={}
    for line in dumped.splitlines():
        fields=shlex.split(line.rstrip(';'))
        if len(fields)==2:effective[fields[0]]=fields[1]
    event['effective']=effective
    event['sources']=pathlib.Path(effective['Dir::Etc::sourcelist']).read_text()
    if os.environ.get('CI_BROWSER_PROBE_APT')=='1':
        lists=config.parent/'lists';(lists/'partial').mkdir(parents=True)
        cache=config.parent/'cache';cache.mkdir()
        probe=subprocess.run(['/usr/bin/apt-get','--print-uris','-o','Dir::State::lists='+str(lists),
                              '-o','Dir::Cache='+str(cache),'update'],check=True,capture_output=True,text=True,timeout=10)
        event['apt_uris']=probe.stdout
else:
    assert phase=='install', phase
record(event)
if os.environ.get('CI_BROWSER_PROBE_FAILURE')==phase:raise SystemExit(17 if phase=='install-deps' else 23)
'''


@unittest.skipUnless(SUPPORTED, 'The dependency helper targets Ubuntu 24.04 Linux jobs only')
class BrowserDependencyInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='studio browser ci ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.bin=self.root/'bin';self.bin.mkdir()
        self.runner=self.root/'runner temp';self.runner.mkdir()
        self.log=self.root/'commands.jsonl'
        for name,source in (('sudo',SUDO),('timeout',TIMEOUT),('python',PYTHON)):
            path=self.bin/name;path.write_text('#!'+sys.executable+'\n'+source);path.chmod(0o755)
        self.env=dict(os.environ,PATH=str(self.bin)+os.pathsep+os.environ['PATH'],RUNNER_TEMP=str(self.runner),
                      CI_BROWSER_PROBE_LOG=str(self.log))
        self.env.pop('APT_CONFIG',None)
        self.env.pop('CI_BROWSER_PROBE_SUDO',None)

    def run_helper(self,**options):
        result=subprocess.run(['bash',str(HELPER)],env=dict(self.env,**options),capture_output=True,text=True,timeout=20)
        events=[json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result,events

    def assert_cleaned(self):self.assertEqual(list(self.runner.iterdir()),[])

    def test_signed_temporary_config_reaches_elevated_dependencies_but_browser_stays_user_owned(self):
        result,events=self.run_helper()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        phases=[event for event in events if event['kind']=='playwright']
        self.assertEqual([event['phase'] for event in phases],['install-deps','install'])
        self.assertTrue(phases[0]['elevated']);self.assertFalse(phases[1]['elevated'])
        self.assertEqual(len([event for event in events if event['kind']=='sudo']),1)
        config=phases[0]
        self.assertTrue(Path(config['apt_config']).is_relative_to(self.runner))
        self.assertEqual(config['effective']['Dir::Etc::parts'],'-')
        self.assertEqual(config['effective']['Dir::Etc::main'],'-')
        self.assertEqual(config['effective']['Dir::Etc::sourceparts'],'-')
        self.assertTrue(Path(config['effective']['Dir::Etc::sourcelist']).is_relative_to(self.runner))
        self.assertEqual(config['effective']['APT::Update::Error-Mode'],'any')
        self.assertLessEqual(int(config['effective']['Acquire::Retries']),1)
        for scheme in ('http','https'):
            self.assertLessEqual(int(config['effective']['Acquire::'+scheme+'::Timeout']),15)
        self.assertEqual(config['sources'].count('Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg'),2)
        self.assertNotIn('Trusted: yes',config['sources'])
        bounds=[event for event in events if event['kind']=='timeout']
        self.assertEqual(len(bounds),2);self.assertTrue(bounds[0]['elevated']);self.assertFalse(bounds[1]['elevated'])
        total=sum(int(event['args'][1][:-1])+int(event['args'][0].split('=')[1][:-1]) for event in bounds)
        self.assertLess(total,240,'The installer must finish before its four-minute step deadline')
        self.assert_cleaned()

    def test_real_apt_selects_only_official_https_noble_archives_without_fetching(self):
        result,events=self.run_helper(CI_BROWSER_PROBE_APT='1')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        dependency=next(event for event in events if event.get('phase')=='install-deps')
        uris=re.findall(r"'(https?://[^']+)'",dependency['apt_uris'])
        self.assertTrue(uris,dependency['apt_uris'])
        self.assertTrue(all(uri.startswith(('https://archive.ubuntu.com/ubuntu/','https://security.ubuntu.com/ubuntu/')) for uri in uris),uris)
        for suite in ('noble','noble-updates','noble-security'):
            self.assertTrue(any('/dists/'+suite+'/' in uri for uri in uris),(suite,uris))
        self.assert_cleaned()

    def test_dependency_failure_stops_browser_install_and_preserves_exit_status(self):
        result,events=self.run_helper(CI_BROWSER_PROBE_FAILURE='install-deps')
        self.assertEqual(result.returncode,17,result.stdout+result.stderr)
        self.assertEqual([event['phase'] for event in events if event['kind']=='playwright'],['install-deps'])
        self.assert_cleaned()

    def test_dependency_timeout_stops_browser_install_and_preserves_exit_status(self):
        result,events=self.run_helper(CI_BROWSER_PROBE_FAILURE='timeout-deps')
        self.assertEqual(result.returncode,124,result.stdout+result.stderr)
        self.assertFalse(any(event['kind']=='playwright' for event in events))
        self.assert_cleaned()

    def test_browser_failure_keeps_normal_user_and_cleans_temporary_config(self):
        result,events=self.run_helper(CI_BROWSER_PROBE_FAILURE='install')
        self.assertEqual(result.returncode,23,result.stdout+result.stderr)
        phases=[event for event in events if event['kind']=='playwright']
        self.assertEqual([event['phase'] for event in phases],['install-deps','install'])
        self.assertFalse(phases[-1]['elevated'])
        self.assert_cleaned()


if __name__=='__main__':unittest.main()
