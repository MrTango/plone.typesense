from typing import Dict
from typing import List
from typing import Tuple
from dataclasses import dataclass
from Products.CMFCore.interfaces import IIndexQueueProcessor
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.interface import Interface

class ITypesenseManager(Interface):
    """
    """

class IPloneTypesenseLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class ITypesenseSearchIndexQueueProcessor(IIndexQueueProcessor):
    """Index queue processor for Typesense."""


@dataclass
class IndexingActions:

    index: Dict[str, dict]
    reindex: Dict[str, dict]
    unindex: Dict[str, dict]
    index_blobs: Dict[str, dict]
    uuid_path: Dict[str, str]

    def __len__(self):
        size = 0
        size += len(self.index)
        size += len(self.reindex)
        size += len(self.unindex)
        return size

    def all(self) -> List[Tuple[str, str, Dict]]:
        all_data = []
        for attr, action in (
            ("index", "index"),
            ("reindex", "update"),
            ("unindex", "delete"),
        ):
            action_data = [
                (uuid, data) for uuid, data in getattr(self, attr, {}).items()
            ]
            if action_data:
                all_data.extend([(action, uuid, data) for uuid, data in action_data])
        return all_data

    # def all_blob_actions(self):
    #     return [(uuid, data) for uuid, data in getattr(self, "index_blobs", {}).items()]
