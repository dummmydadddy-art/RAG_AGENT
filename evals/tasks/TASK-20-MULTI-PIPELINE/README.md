# Task Specification: Streaming Dataflow Pipeline with Tumbling Windows

## 1. Multi-Module Architecture
Implement modules in `src/dataflow/`:
- `window.py`: `TumblingWindow(window_size_seconds)` grouping items by event timestamp.
- `stages.py`: `MapStage`, `FilterStage`, `AggregateStage`.
- `pipeline.py`: `DataflowPipeline` linking stages and executing stream processing.

### Pipeline Contract
```python
class DataflowPipeline:
    def __init__(self) -> None:
    def add_stage(self, stage: Any) -> "DataflowPipeline":
    def process(self, records: List[Dict[str, Any]]) -> List[Any]:
```
