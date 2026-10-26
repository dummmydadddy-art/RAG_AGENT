# Task Specification: Prefix Trie with Autocomplete and Longest Prefix

## 1. Class Contract
Implement `PrefixTrie` in `src/prefix_trie.py`.

### Constructor Signature
```python
def __init__(self) -> None:
```
Initializes an empty prefix trie.

### Methods
1. `insert(self, word: str, value: Any = None) -> None`:
   - Inserts string `word` into trie associated with optional `value`.
   - If `word` is empty (`""`), raise `ValueError("Word cannot be empty")`.
   - If `not isinstance(word, str)`, raise `TypeError("Word must be a string")`.
   - If `word` already exists, updates associated value.

2. `search(self, word: str) -> Optional[Any]`:
   - Returns associated value if exact `word` is in trie; returns `None` if absent.

3. `starts_with(self, prefix: str) -> bool`:
   - Returns `True` if any inserted word starts with `prefix`; `True` if `prefix == ""` and trie non-empty; `False` otherwise.

4. `autocomplete(self, prefix: str, limit: int = 10) -> List[Tuple[str, Any]]`:
   - Returns up to `limit` words beginning with `prefix` and their values, sorted lexicographically by word.

5. `longest_prefix_of(self, word: str) -> str`:
   - Returns the longest matching word stored in the trie that is a prefix of `word`. Returns `""` if none match.
