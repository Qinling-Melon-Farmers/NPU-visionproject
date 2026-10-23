import json
from pathlib import Path
import tempfile
import unittest

from vision.scripts.audit_interactions import collect, classify


class InteractionTests(unittest.TestCase):
    def test_child_user_role_is_not_student(self):
        self.assertEqual(classify('/root/image_experiment','user')[0],'agent_collaboration')
        self.assertEqual(classify('/root','user')[1],'student')

    def test_structured_answers_encryption_and_mirrors(self):
        def event(seconds,kind,payload):
            return {'timestamp':f'2026-10-23T06:00:{seconds:02d}.000Z','type':kind,'payload':payload}
        rows=[event(0,'turn_context',{'model':'example-main-model'}),
              event(1,'event_msg',{'type':'user_message','message':'重复提示'}),
              event(1,'response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'重复提示'}]}),
              event(5,'event_msg',{'type':'user_message','message':'重复提示'}),
              event(6,'response_item',{'type':'function_call','name':'request_user_input','call_id':'q','arguments':json.dumps({'questions':[{'question':'选择数据'}]})}),
              event(7,'response_item',{'type':'function_call_output','call_id':'q','output':'{"answers":{"data":"public"}}'}),
              event(8,'response_item',{'type':'function_call','name':'spawn_agent','call_id':'a','arguments':json.dumps({'task_name':'test','model':'gpt-6.1-sol','fork_turns':'none','message':'gAAAAAencrypted'})}),
              event(9,'response_item',{'type':'message','role':'assistant','channel':'analysis','content':[{'type':'output_text','text':'hidden text must not be exported'}]}),
              event(10,'response_item',{'type':'message','role':'developer','content':[{'type':'input_text','text':'internal instruction'}]})]
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'session.jsonl'
            path.write_text('\n'.join(json.dumps(x) for x in rows),encoding='utf-8')
            messages,sources,spawns,receipts=collect(path)
        self.assertEqual(sum(x['kind']=='visible_message' for x in messages),2)
        self.assertEqual(sum(x['kind']=='structured_answer' and x['sender']=='student' for x in messages),1)
        coordination=[x for x in messages if x['category']=='agent_collaboration']
        self.assertEqual(len(coordination),1)
        self.assertFalse(coordination[0]['body_available'])
        self.assertNotIn('gAAAAAencrypted',json.dumps(messages))
        self.assertNotIn('hidden text',json.dumps(messages))
        self.assertNotIn('internal instruction',json.dumps(messages))
        self.assertTrue(all(x['model']=='not_applicable_human' for x in messages if x['sender']=='student'))


if __name__=='__main__':unittest.main()
