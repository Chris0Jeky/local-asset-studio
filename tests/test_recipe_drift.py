import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import recipe_drift


def node(class_type='KSampler', **inputs): return {'class_type':class_type,'inputs':inputs}


class RecipeDriftTests(unittest.TestCase):
    def test_changed_literal(self):
        self.assertEqual(recipe_drift.summary({'3':node(steps=30)}, {'3':node(steps=25)}), 'node 3 KSampler steps 30→25')

    def test_removed_node(self):
        self.assertEqual(recipe_drift.summary({'12':node('LoraLoader')}, {}), 'node 12 LoraLoader removed')

    def test_added_node(self):
        self.assertEqual(recipe_drift.summary({}, {'4':node('CheckpointLoaderSimple')}), 'node 4 CheckpointLoaderSimple added')

    def test_class_change(self):
        self.assertEqual(recipe_drift.summary({'3':node()}, {'3':node('KSamplerAdvanced')}), 'node 3 class_type KSampler→KSamplerAdvanced')

    def test_long_text_and_short_prompts_are_redacted(self):
        for field, before, after in (('description','secret'*10,'private'*10), ('text','old prompt','new prompt'), ('text_g','old','new'), ('positive','old','new'), ('string','old','new')):
            with self.subTest(field=field):
                result=recipe_drift.summary({'1':node('CLIPTextEncode', **{field:before})}, {'1':node('CLIPTextEncode', **{field:after})})
                self.assertEqual(result, f'node 1 CLIPTextEncode {field} text changed')
                self.assertNotIn(before,result);self.assertNotIn(after,result)

    def test_model_filenames_use_basename(self):
        result=recipe_drift.summary({'4':node('CheckpointLoaderSimple',ckpt_name='C:\\private\\models\\a.safetensors')}, {'4':node('CheckpointLoaderSimple',ckpt_name='/private/models/b.safetensors')})
        self.assertEqual(result,'node 4 CheckpointLoaderSimple ckpt_name a.safetensors→b.safetensors')

    def test_link_inputs_ignored_unless_target_changes(self):
        old={'3':node(model=['1',0],steps=30)};new=copy.deepcopy(old);new['3']['inputs']['steps']=25
        self.assertEqual(recipe_drift.summary(old,new),'node 3 KSampler steps 30→25')
        new=copy.deepcopy(old);new['3']['inputs']['model']=['2',0]
        self.assertEqual(recipe_drift.summary(old,new),'node 3 KSampler model link changed')
        new['3']['inputs']['model']=['1',1]
        self.assertEqual(recipe_drift.summary(old,new),'node 3 KSampler model link changed')

    def test_input_added_and_removed(self):
        self.assertEqual(recipe_drift.summary({'1':node(cfg=7)}, {'1':node(steps=25)}),'node 1 KSampler cfg removed; node 1 KSampler steps added')

    def test_cap_and_numeric_aware_order(self):
        old={str(i):node(steps=30) for i in (12,10,6,5,4,3,2,1)};new={key:node(steps=25) for key in old}
        result=recipe_drift.summary(old,new)
        self.assertEqual(result,'; '.join(f'node {i} KSampler steps 30→25' for i in range(1,7))+'; +2 more')
        self.assertLess(len(result),400)
        self.assertEqual(result,recipe_drift.summary(dict(reversed(list(old.items()))),new))

    def test_character_budget_counts_omitted_items(self):
        old={str(i):node('K'*200,**{'x'*100:30}) for i in range(10)};new={key:node('K'*200,**{'x'*100:25}) for key in old}
        result=recipe_drift.summary(old,new);shown=result.count('node ')
        self.assertLess(len(result),400);self.assertGreater(shown,0);self.assertLessEqual(shown,6)
        self.assertTrue(result.endswith(f'+{10-shown} more'))

    def test_identical_graphs(self):
        graph={'3':node(steps=30,model=['1',0])}
        self.assertEqual(recipe_drift.summary(graph,copy.deepcopy(graph)),'')


if __name__ == '__main__': unittest.main()
