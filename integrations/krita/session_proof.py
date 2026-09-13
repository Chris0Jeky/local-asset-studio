"""Fixed native API proof on a newly authored disposable document only.

Invoke through configured kritarunner with one NEW output directory. This is
mechanical evidence, not a generated character or a GUI interaction benchmark.
"""
import json
from pathlib import Path
import sys

from . import document_session as ds
from . import native_edit as native


def run(args):
    native.need(len(args) == 1, 'One new native proof directory required')
    root = ds.checked_path(args[0]); root.mkdir()
    ds.publish(root/'proof-intent.json', ds.canonical({'kind':'krita_document_session_fixture','neural_inference':False}) + b'\n')
    from krita import Krita, Selection, InfoObject
    app = Krita.instance(); doc = None
    try:
        width,height = 384,256
        doc = app.createDocument(width,height,'Studio native session fixture','RGBA','U8',native.PROFILE,72.0)
        native.need(doc is not None, 'Krita did not create the owned fixture')
        doc.setBatchmode(True)
        # Two authored figures and a separate hidden layer. No model is involved.
        source = bytearray(bytes([42,36,28,255]) * width * height)
        def fill(buffer, box, color):
            left,top,right,bottom = box
            for y in range(top,bottom):
                for x in range(left,right):
                    offset = (y*width+x)*4; buffer[offset:offset+4] = bytes(color)
        fill(source,(64,56,128,216),(140,86,26,255))
        fill(source,(240,64,312,208),(64,160,206,255))
        hidden = doc.createNode('Hidden retained drawing','paintlayer')
        native.need(doc.rootNode().addChildNode(hidden,None), 'Cannot add hidden fixture layer')
        hidden.setPixelData(bytes([7,11,13,255])*4,-2,0,2,2); hidden.setVisible(False)
        visible = doc.createNode('Two authored figures','paintlayer')
        native.need(doc.rootNode().addChildNode(visible,hidden), 'Cannot add visible fixture layer')
        visible.setPixelData(bytes(source),0,0,width,height)
        selection = Selection(); selection.select(72,104,48,84,255); doc.setSelection(selection)
        doc.setModified(True)
        doc.waitForDone(); doc.refreshProjection(); doc.waitForDone()
        session = ds.Session(doc)
        capture = session.capture(root/'capture')
        native.need(doc.modified() and doc.fileName() == '', 'Capture changed unsaved source ownership')
        native.need(ds.read_file(root/'capture/source.bgra') == bytes(source), 'Captured source pixels changed')
        original = session.inspect()
        result = bytearray(source); fill(result,(72,104,120,188),(186,190,224,255))
        overlay = bytearray(len(source))
        for offset in range(0,len(source),4):
            if result[offset:offset+4] != source[offset:offset+4]: overlay[offset:offset+4] = result[offset:offset+4]
        package = root/'package'; package.mkdir()
        buffers = {'native-source.kra': ds.read_file(root/'capture/source.kra'), 'source.bgra':bytes(source),
                   'result.bgra':bytes(result), 'overlay.bgra':bytes(overlay)}
        plan = {'schema_version':1,'operation':'character.krita-layer.v1','canvas':[width,height],
                'profile':native.PROFILE,'edit_plan_sha256':native.digest(bytes(overlay)),
                'changed_pixels':48*84,'semantic_approval':False,'neural_inference':False,
                'files':{name:{'bytes':len(raw),'sha256':native.digest(raw)} for name,raw in buffers.items()}}
        for name,raw in buffers.items(): ds.publish(package/name,raw)
        ds.publish(package/'native-plan.json',ds.canonical(plan)+b'\n')
        ds.prepare_request(root/'capture/snapshot.json',package/'native-plan.json',root/'import.json')
        # A changed off-canvas hidden pixel is invisible in the projection.
        before_hidden = bytes(hidden.pixelData(-2,0,2,2))
        hidden.setPixelData(bytes([9,11,13,255])*4,-2,0,2,2)
        doc.waitForDone(); doc.refreshProjection(); doc.waitForDone()
        native.need(bytes(doc.pixelData(0,0,width,height)) == bytes(source), 'Hidden fixture unexpectedly changed visible pixels')
        try: session.import_request(root/'import.json')
        except ValueError as exc:
            native.need('stale' in str(exc), 'Unexpected stale-import rejection: '+str(exc))
            stale_error = str(exc)
        else: raise ValueError('Native import accepted stale hidden pixels')
        native.need(len(doc.topLevelNodes()) == len(original['document']['node_order']) and not (package/'live-intent.json').exists(), 'Stale import changed document or recorded an attempt')
        # Restore only this test's known pixel mutation, then use the retained request.
        hidden.setPixelData(before_hidden,-2,0,2,2)
        doc.waitForDone(); doc.refreshProjection(); doc.waitForDone()
        imported = session.import_request(root/'import.json')
        native.need(doc.modified() and doc.fileName() == '', 'Import changed unsaved source ownership')
        native.need(bytes(doc.pixelData(0,0,width,height)) == bytes(result), 'Native result is not exact')
        native.need(doc.exportImage(str(root/'result.png'),InfoObject()), 'Cannot export native result proof')
        session.show_source()
        native.need(bytes(doc.pixelData(0,0,width,height)) == bytes(source), 'Native source comparison is not exact')
        native.need(doc.exportImage(str(root/'source.png'),InfoObject()), 'Cannot export source comparison')
        session.show_result()
        proposed = next(node for node in doc.topLevelNodes() if str(node.uniqueId()) == imported['layer_id'])
        proposed.setPixelData(bytes([1,2,3,255]),72,104,1,1)
        doc.waitForDone(); doc.refreshProjection(); doc.waitForDone()
        try: session.show_source()
        except ValueError as exc:
            native.need('stale' in str(exc), 'Unexpected stale-compare rejection: '+str(exc))
            compare_error = str(exc)
        else: raise ValueError('Native comparison discarded a later proposed-layer edit')
        native.need(proposed.visible(), 'Stale comparison hid the user-edited layer')
        # Save only an owned clone for inspection, retaining the simulated user edit.
        clone = doc.clone()
        try:
            clone.setBatchmode(True)
            native.need(clone.saveAs(str(root/'retained-unsaved-edit.kra')), 'Cannot retain native fixture clone')
        finally:
            clone.setModified(False); clone.close()
        receipt = {'schema_version':1,'kind':'krita_document_session_proof','krita_version':app.version(),
                   'python_version':sys.version,'canvas':[width,height],'changed_pixels':48*84,
                   'unsaved_source_preserved':doc.modified() and doc.fileName() == '',
                   'hidden_off_canvas_change_rejected':stale_error,'proposed_layer_change_rejected':compare_error,
                   'source_result_comparison_exact':True,'imported':imported,
                   'neural_inference':False,'semantic_approval':False,'gui_interaction_verified':False,
                   'outputs':{name:ds.record(root/name) for name in ('result.png','source.png','retained-unsaved-edit.kra')}}
        ds.publish(root/'proof-result.json',ds.canonical(receipt)+b'\n')
        return receipt
    except Exception as exc:
        ds.publish(root/'proof-failure.json',ds.canonical({'error':str(exc)})+b'\n')
        raise
    finally:
        if doc is not None:
            doc.setModified(False); doc.close()  # This harness owns this created fixture only.
