from typing import Any, Dict, List, Optional, Tuple


class TrieNode:
    def __init__(self) -> None:
        self.children: Dict[str, TrieNode] = {}
        self.is_end: bool = False
        self.value: Optional[Any] = None


class PrefixTrie:
    """
    Prefix Trie supporting autocomplete, prefix matching, and longest prefix matching.
    """

    def __init__(self) -> None:
        self.root = TrieNode()
        self._size = 0

    def insert(self, word: str, value: Any = None) -> None:
        if not isinstance(word, str):
            raise TypeError("Word must be a string")
        if not word:
            raise ValueError("Word cannot be empty")

        curr = self.root
        for ch in word:
            if ch not in curr.children:
                curr.children[ch] = TrieNode()
            curr = curr.children[ch]

        if not curr.is_end:
            self._size += 1
        curr.is_end = True
        curr.value = value

    def search(self, word: str) -> Optional[Any]:
        if not isinstance(word, str) or not word:
            return None
        curr = self.root
        for ch in word:
            if ch not in curr.children:
                return None
            curr = curr.children[ch]
        return curr.value if curr.is_end else None

    def starts_with(self, prefix: str) -> bool:
        if not isinstance(prefix, str):
            return False
        if prefix == "":
            return self._size > 0
        curr = self.root
        for ch in prefix:
            if ch not in curr.children:
                return False
            curr = curr.children[ch]
        return True

    def autocomplete(self, prefix: str, limit: int = 10) -> List[Tuple[str, Any]]:
        if not isinstance(prefix, str) or limit <= 0:
            return []

        curr = self.root
        for ch in prefix:
            if ch not in curr.children:
                return []
            curr = curr.children[ch]

        results: List[Tuple[str, Any]] = []

        def _dfs(node: TrieNode, current_word: str):
            if len(results) >= limit:
                return
            if node.is_end:
                results.append((current_word, node.value))
            # Sort keys for deterministic lexicographical ordering
            for char in sorted(node.children.keys()):
                if len(results) >= limit:
                    break
                _dfs(node.children[char], current_word + char)

        _dfs(curr, prefix)
        return results

    def longest_prefix_of(self, word: str) -> str:
        if not isinstance(word, str) or not word:
            return ""

        curr = self.root
        longest = ""
        prefix_acc = ""

        for ch in word:
            if ch not in curr.children:
                break
            curr = curr.children[ch]
            prefix_acc += ch
            if curr.is_end:
                longest = prefix_acc

        return longest
