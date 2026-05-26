# 文件说明：检索器基类。



from dataclasses import dataclass,field
from typing import Optional,Any

class Document:
    """文档对象，用于表示检索到的文档内容。

    """
    id: str = ""
    content: str = ""
    metadata: dict[str,Any] = field(default_factory=dict)

@dataclass
class SearchResult:
    """搜索结果。
    
    支持两种构造方式：
    1. 新方式：SearchResult(text="...", score=0.9)
    2. 旧方式：SearchResult(document=Document(...), score=0.9)
    
    Attributes:
        text: 检索到的文本内容
        metadata: 元数据（来源、页码等）
        score: 相似度分数
        document: 向后兼容的Document对象
    """    
    text: str = ""
    metadata: dict = field(default_factory=dict)
    score:Optional[float] = None
    document:Optional[Document] = None

    def __repr__(self) -> str:
        """初始化后处理，兼容旧的document对象"""
        if self.document is not None and not self.text:
            self.text = self.document.content
            if not self.metadata:
                self.metadata = self.document.metadata.copy()
        
    @property
    def source(self) -> str:
        """获取来源信息"""
        return self.metadata.get("source","unknown")
    
    @property
    def content(self) -> str:
        """获取文本内容"""
        return self.text