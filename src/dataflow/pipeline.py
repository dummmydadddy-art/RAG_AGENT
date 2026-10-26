from typing import Any, Dict, List


class DataflowPipeline:
    """
    Linear streaming pipeline orchestrating sequential processing stages and windows.
    """

    def __init__(self) -> None:
        self.stages: List[Any] = []

    def add_stage(self, stage: Any) -> "DataflowPipeline":
        self.stages.append(stage)
        return self

    def process(self, records: List[Dict[str, Any]]) -> List[Any]:
        current = list(records)
        for stage in self.stages:
            if hasattr(stage, "process"):
                current = stage.process(current)
            elif callable(stage):
                current = stage(current)
        return current
