"""Pure telemetry tests: no model calls, simulation runs, or usage estimation."""
import unittest
from scripts.summarize_instrumentation_sanity import usage, inference_spans

class NativeTelemetryTests(unittest.TestCase):
    def test_breakdowns_not_double_counted(self):
        result=usage(dict(inputTokens=100,cachedInputTokens=80,cacheWriteInputTokens=0,
                          outputTokens=20,reasoningOutputTokens=15,totalTokens=120))
        self.assertEqual(result['total_tokens'],120)

    def test_missing_usage_rejected(self):
        with self.assertRaises(ValueError):usage({'inputTokens':100,'outputTokens':20})

    def test_inconsistent_total_rejected(self):
        with self.assertRaises(ValueError):
            usage(dict(inputTokens=100,cachedInputTokens=80,cacheWriteInputTokens=0,
                       outputTokens=20,reasoningOutputTokens=15,totalTokens=215))

    def test_native_warmup_is_not_inference(self):
        spans=[]
        for i,warmup in enumerate([True,False]):
            spans.append({'spanId':str(i),'attributes':[{'key':'websocket.warmup','value':{'boolValue':warmup}}],'name':'parent'})
            spans.append({'spanId':str(i+2),'parentSpanId':str(i),'name':'responses_websocket.stream_request','startTimeUnixNano':str(i+100)})
        self.assertEqual([s['spanId'] for s,a in inference_spans(spans)],['3'])

if __name__=='__main__':unittest.main()
