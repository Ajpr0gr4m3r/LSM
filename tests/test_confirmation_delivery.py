import unittest
from unittest.mock import patch
from web_app import Runtime

class ConfirmationDeliveryTests(unittest.TestCase):
    def test_replays_same_verified_event_until_acknowledged(self):
        runtime=Runtime()
        sid=runtime.new_session('lsm')
        payload={'session':sid,'confirmation_ack':None}
        verified={'confirmed':{'id':'b','text':'B'},'confidence':.99}
        with patch.object(runtime,'_frame',side_effect=[
            verified, {'confirmed':None,'inference_skipped':True},
            {'confirmed':None}, {'confirmed':None}]):
            first=runtime.frame(payload)
            replay=runtime.frame(payload)
            self.assertEqual(first['confirmation_id'],replay['confirmation_id'])
            self.assertEqual(replay['confirmed']['text'],'B')
            self.assertEqual(replay['confirmed_confidence'],.99)
            acknowledged=runtime.frame({**payload,'confirmation_ack':first['confirmation_id']})
            self.assertIsNone(acknowledged['confirmed'])
            self.assertNotIn('confirmation_id',runtime.frame(payload))

    def test_legacy_clients_do_not_receive_repeated_events(self):
        runtime=Runtime()
        with patch.object(runtime,'_frame',return_value={'confirmed':None}) as handler:
            self.assertEqual(runtime.frame({}),{'confirmed':None})
            handler.assert_called_once()
