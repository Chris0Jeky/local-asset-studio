"""Additional malformed-input guards; no model or media generation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_prompt.core import new_brief
from studio_prompt.metadata import inflate
from studio_prompt.local_helper import run_local

class GuardTests(unittest.TestCase):
    def test_invalid_deflate_is_a_controlled_validation_error(self):
        with self.assertRaises(ValueError):inflate(b'not-zlib-data')

    def test_nonobject_helper_change_is_rejected(self):
        value={'changes':['not an object'],'observations':[],'unknowns':[]}
        with tempfile.TemporaryDirectory() as root:
            with patch('studio_prompt.local_helper.http_json',side_effect=[{'models':[{'name':'local','digest':'test'}]},{'done':True,'message':{'content':json.dumps(value)}}]):
                with self.assertRaises(ValueError):run_local(new_brief('Keeper'),'local',root=root,idle_confirmed=True)

    def test_reference_evidence_requires_image_input(self):
        brief=new_brief('Keeper')
        brief['references']=[{'id':'pose-a','role':'pose','kind':'image','path':'unused.png','sha256':'a'*64,'take':['pose'],'ignore':[]}]
        value={'changes':[{'field':'facets.action','value':'Standing','reason':'Visible pose','source':'pose-a'}],'observations':[],'unknowns':[]}
        with tempfile.TemporaryDirectory() as root:
            with patch('studio_prompt.local_helper.http_json',side_effect=[{'models':[{'name':'local','digest':'test'}]},{'done':True,'message':{'content':json.dumps(value)}}]):
                with self.assertRaises(ValueError):run_local(brief,'local',root=root,idle_confirmed=True)

if __name__=='__main__':unittest.main()
