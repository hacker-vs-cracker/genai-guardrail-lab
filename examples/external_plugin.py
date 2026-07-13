"""Minimal example of an external evaluator plugin."""

from genai_guardrail_lab.evaluators.base import BaseEvaluator
from genai_guardrail_lab.models import Evaluation, RenderedScenario, TargetResponse
from genai_guardrail_lab.registry import EVALUATOR_REGISTRY


@EVALUATOR_REGISTRY.register("response_length")
class ResponseLengthEvaluator(BaseEvaluator):
    def evaluate(self, scenario: RenderedScenario, response: TargetResponse) -> Evaluation:
        if response.error:
            return Evaluation("ERROR", 0, ["target_error"], response.error)
        if len(response.text) > 2000:
            return Evaluation("REVIEW", 30, ["unusually_long_response"])
        return Evaluation("PASS", 0, ["response_length_expected"])
