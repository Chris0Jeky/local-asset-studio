from pathlib import Path
import subprocess
def blob(name):return subprocess.check_output(['git','hash-object',name],text=True).strip()
assert blob('app/static/studio-workbench.js')=='c878444a2a7628eed287de08948244e9fca94a55'
assert blob('tests/workshop_recipe_wording.py')=='4dbbded65b5d101484740aed33a2c634e389cfc3'
p=Path('app/static/studio-workbench.js');s=p.read_text()
replacements=[
("const pictureStamp=()=>JSON.stringify([selected?.id,wording(),q('#batch')?.value,", "const pictureStamp=()=>JSON.stringify([selected?.id,wording(),values(),recipeTemplateHash,q('#batch')?.value,"),
("const pictureSnapshot=()=>({id:selected.id,name:selected.name,controls:values(),", "const pictureSnapshot=()=>({id:selected.id,name:selected.name,templateHash:recipeTemplateHash,controls:values(),"),
("wordingBack.onclick=()=>{const pic=pictureKept;", "wordingBack.onclick=()=>{if(referencePending>0){announce('Wait for the picture upload to finish before going back. Nothing was replaced.',true);return;}const pic=pictureKept;"),
("uploaded=pic.uploaded;lastUploaded=pic.lastUploaded;parentAssets=", "recipeTemplateHash=pic.templateHash;uploaded=pic.uploaded;lastUploaded=pic.lastUploaded;parentAssets="),
("q('#positive').dispatchEvent(new Event('input',{bubbles:true}));if(typeof renderReferenceSlots==='function')renderReferenceSlots();", "updateLoraHints();q('#positive').dispatchEvent(new Event('input',{bubbles:true}));if(typeof renderReferenceSlots==='function')renderReferenceSlots();"),
("if(e.target.closest('[data-variant],#randomSeed,[data-ref-clear],[data-ref-up],[data-ref-down]')){draftDirty=true;", "if(e.target.closest('[data-variant],#randomSeed,[data-ref-clear],[data-ref-up],[data-ref-down]')){pictureKept=null;renderUndo();draftDirty=true;")]
for old,new in replacements:
 assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
p.write_text(s)
p=Path('tests/workshop_recipe_wording.py');s=p.read_text();marker="if __name__ == '__main__':"
extra='''    def test_picture_way_back_preserves_template_identity_and_refreshes_adapter_hints(self):
        self.stage_picture()
        self.page.evaluate("recipeTemplateHash='a'.repeat(64);window.hintCalls=0;const originalHints=updateLoraHints;updateLoraHints=function(){hintCalls++;return originalHints();}")
        self.switch('sdxl')
        self.page.locator('#uxWordingUndoBack').wait_for(state='visible')
        self.page.evaluate('hintCalls=0')
        self.page.click('#uxWordingUndoBack')
        self.assertEqual(self.page.evaluate('recipeTemplateHash'), 'a'*64)
        self.assertEqual(self.page.evaluate('StudioSetupDraft.capture().templateHash'), 'a'*64)
        self.assertGreater(self.page.evaluate('hintCalls'), 0)

    def test_picture_way_back_does_not_abort_an_in_flight_upload(self):
        self.stage_picture()
        self.switch('qwen-2ref')
        self.page.locator('#uxWordingUndoBack').wait_for(state='visible')
        self.page.evaluate('referencePending=1')
        epoch = self.page.evaluate('referenceEpoch')
        self.page.click('#uxWordingUndoBack')
        self.assertEqual(self.page.evaluate('selected.id'), 'qwen-2ref')
        self.assertEqual(self.page.evaluate('referenceEpoch'), epoch)
        self.assertIn('upload', self.page.locator('#uxNotice').inner_text())
        self.assertTrue(self.page.locator('#uxWordingUndoBack').is_visible())
        self.page.evaluate('referencePending=0')
        self.page.click('#uxWordingUndoBack')
        self.assertEqual(self.page.evaluate('selected.id'), 'gentle-variation')

    def test_click_only_seed_and_variant_edits_withdraw_picture_way_back(self):
        for selector in ('#randomSeed', '[data-variant="0"]'):
            with self.subTest(selector=selector):
                self.stage_picture()
                self.switch('sdxl')
                self.page.locator('#uxWordingUndoBack').wait_for(state='visible')
                self.page.locator(selector).click()
                self.assertTrue(self.page.locator('#uxWordingUndoBack').is_hidden())
                self.assertEqual(self.page.evaluate('selected.id'), 'sdxl')

'''
assert s.count(marker)==1;s=s.replace(marker,extra+marker);p.write_text(s)
expected={'app/static/studio-workbench.js':'75f1a916f7ee25d64d97bcc775635641e9e9de78','tests/workshop_recipe_wording.py':'37454fc8edc49c15cb6daf9391e5ff3bb910b795','tests/picture_wayback.cjs':'1d1477c4a8953556ec23451cf00b610b47cbd451','tests/test_picture_wayback.py':'7eedf50b974b9ff3e601aebe877731600da7e80f'}
for name,wanted in expected.items():assert blob(name)==wanted,('output drift',name,blob(name))
