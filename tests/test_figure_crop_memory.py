"""One-crop lifetime contracts; actual Pillow encodes and content-addressed files."""
from contextlib import closing
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_workflow import addressable_figures as figures


class WorkspaceError(ValueError):
    pass


class SnapshotWorkspace:
    def __init__(self, root):
        self.root = Path(root); self.media = self.root / 'media'; self.media.mkdir()

    def _verify_snapshot(self, path, digest):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise WorkspaceError('snapshot integrity')


def rectangles(count=4):
    return [{'x': i * 10000 // count, 'y': 0, 'width': 10000 // count, 'height': 10000}
            for i in range(count)]


class FigureCropMemoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.workspace = SnapshotWorkspace(temporary.name)

    def canvas(self, mode='RGBA', size=(101, 79)):
        image = Image.new(mode, size)
        data = [(x * 17 % 256, y * 31 % 256, (x+y) * 7 % 256, (0,127,255)[x % 3])
                for y in range(size[1]) for x in range(size[0])]
        image.putdata([value if mode == 'RGBA' else value[:3] for value in data])
        image.info['icc_profile'] = b'synthetic profile'
        return image

    def test_each_snapshot_precedes_next_crop_and_only_metadata_is_retained(self):
        events=[]; original_crop=Image.Image.crop; original_snapshot=figures._snapshot_png
        def crop(image, box):
            events.append('crop'); return original_crop(image, box)
        def snapshot(workspace, data):
            events.append('snapshot'); return original_snapshot(workspace, data)
        canvas=self.canvas()
        with patch.object(Image.Image, 'crop', crop), patch.object(figures, '_snapshot_png', snapshot):
            size, rows=figures._encode_crops(self.workspace, canvas, rectangles())
        self.assertEqual(events, ['crop','snapshot']*4)
        self.assertEqual(size, (101,79))
        self.assertTrue(all(isinstance(row[2], tuple) and len(row[2]) == 3 for row in rows))
        self.assertTrue(all(isinstance(row[2][0], str) for row in rows))

    def test_aggregate_budget_is_checked_before_any_crop_or_write(self):
        canvas=self.canvas()
        with patch.object(figures, 'MAX_AGGREGATE_CROP_PIXELS', 3000), \
             patch.object(Image.Image, 'crop', wraps=canvas.crop) as crop, \
             patch.object(figures, '_snapshot_png', wraps=figures._snapshot_png) as snapshot:
            with self.assertRaisesRegex(WorkspaceError, 'aggregate'):
                figures._encode_crops(self.workspace, canvas, rectangles())
        self.assertEqual(crop.call_count, 0)
        self.assertEqual(snapshot.call_count, 0)
        self.assertEqual(list(self.workspace.media.iterdir()), [])
        with self.assertRaises(ValueError): canvas.getpixel((0,0))

    def test_encoded_bytes_pixels_metadata_and_box_order_match_original(self):
        for mode in ('RGB','RGBA'):
            with self.subTest(mode=mode), closing(self.canvas(mode)) as source:
                expected=[]
                for rectangle in rectangles():
                    box=figures._pixel_box(self.workspace, rectangle, *source.size)
                    with closing(source.crop(tuple(box[k] for k in ('left','top','right','bottom')))) as crop:
                        with io.BytesIO() as buffer:
                            crop.save(buffer,format='PNG',optimize=False,compress_level=6)
                            expected.append((rectangle,box,buffer.getvalue(),crop.tobytes()))
                size,rows=figures._encode_crops(self.workspace, source.copy(), rectangles())
                for row, (rectangle,box,encoded,pixels) in zip(rows,expected):
                    self.assertEqual(row[:2], (rectangle,box))
                    self.assertIsInstance(row[2], tuple)
                    path,digest,count=row[2]
                    actual=(self.workspace.root/path).read_bytes()
                    self.assertEqual(actual,encoded)
                    self.assertEqual(digest,hashlib.sha256(encoded).hexdigest())
                    self.assertEqual(count,len(encoded))
                    with Image.open(self.workspace.root/path) as image:
                        self.assertEqual(image.tobytes(),pixels)
                        self.assertEqual(image.info['icc_profile'],b'synthetic profile')

    def test_duplicate_crops_reuse_snapshot_without_dropping_order(self):
        repeated=[dict(x=0,y=0,width=10000,height=10000)]*3
        _,rows=figures._encode_crops(self.workspace,self.canvas(),repeated)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0][2],rows[1][2])
        self.assertEqual(len(list(self.workspace.media.glob('*.png'))),1)
        self.assertEqual(list(self.workspace.media.glob('*.part')),[])

    def test_success_and_encode_error_close_canvas_crop_and_buffer(self):
        for fails in (False,True):
            with self.subTest(fails=fails):
                canvas=self.canvas(); crops=[]; buffers=[]; original=Image.Image.crop; save=Image.Image.save
                def crop(image,box):
                    result=original(image,box);crops.append(result);return result
                def encode(image,buffer,*args,**kwargs):
                    buffers.append(buffer)
                    if fails: raise OSError('injected encode failure')
                    return save(image,buffer,*args,**kwargs)
                with patch.object(Image.Image,'crop',crop),patch.object(Image.Image,'save',encode):
                    if fails:
                        with self.assertRaisesRegex(OSError,'injected'):
                            figures._encode_crops(self.workspace,canvas,rectangles())
                    else: figures._encode_crops(self.workspace,canvas,rectangles())
                for image in [canvas,*crops]:
                    with self.assertRaises(ValueError):image.getpixel((0,0))
                self.assertTrue(all(buffer.closed for buffer in buffers))

    def test_snapshot_error_stops_next_encode_and_cleans_part_file(self):
        canvas=self.canvas(); original=figures._snapshot_png; calls=[]
        def snapshot(workspace,data):
            calls.append(len(data))
            if len(calls)==2: raise OSError('injected snapshot failure')
            return original(workspace,data)
        with patch.object(figures,'_snapshot_png',snapshot):
            with self.assertRaisesRegex(OSError,'injected'):
                figures._encode_crops(self.workspace,canvas,rectangles())
        self.assertEqual(len(calls),2)
        self.assertEqual(len(list(self.workspace.media.glob('*.png'))),1)
        self.assertEqual(list(self.workspace.media.glob('*.part')),[])
        with self.assertRaises(ValueError):canvas.getpixel((0,0))

    def test_snapshot_receives_view_not_copied_encoded_payload(self):
        original=figures._snapshot_png; views=[]
        def snapshot(workspace,data):
            self.assertIsInstance(data,memoryview);views.append(data)
            return original(workspace,data)
        with patch.object(figures,'_snapshot_png',snapshot):
            figures._encode_crops(self.workspace,self.canvas(),rectangles())
        self.assertEqual(len(views),4)
        for view in views:
            with self.assertRaises(ValueError):len(view)

    def test_all_thirty_two_crops_produce_small_ordered_records(self):
        with closing(self.canvas(size=(1024,5))) as source:
            _,rows=figures._encode_crops(self.workspace,source.copy(),rectangles(32))
            self.assertEqual(len(rows),32)
            self.assertEqual([row[0] for row in rows],rectangles(32))
            self.assertTrue(all(isinstance(row[2],tuple) for row in rows))
            self.assertEqual(source.size,(1024,5))

    def test_fsync_error_removes_temporary_file_and_closes_image(self):
        canvas=self.canvas()
        with patch.object(figures.os,'fsync',side_effect=OSError('injected disk failure')):
            with self.assertRaisesRegex(OSError,'injected'):
                figures._encode_crops(self.workspace,canvas,rectangles())
        self.assertEqual(list(self.workspace.media.iterdir()),[])
        with self.assertRaises(ValueError):canvas.getpixel((0,0))


if __name__=='__main__':unittest.main()
