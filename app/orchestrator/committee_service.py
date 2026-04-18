from __future__ import annotations

from typing import Protocol

from app.schemas.committee import CommitteeDraftV1, CommitteeResultV1, CommitteeReviewV1


class CommitteeDraftClientProtocol(Protocol):
    def committee_draft(self, context: dict) -> dict: ...


class CommitteeReviewClientProtocol(Protocol):
    def committee_review(self, draft: dict, context: dict) -> dict: ...


class CommitteeFinalizeClientProtocol(Protocol):
    def committee_finalize(self, draft: dict, review: dict, context: dict) -> dict: ...


class CommitteeDraftService:
    def __init__(self, client: CommitteeDraftClientProtocol) -> None:
        self._client = client

    def build_draft(self, context: dict) -> CommitteeDraftV1:
        payload = self._client.committee_draft(context)
        return CommitteeDraftV1.model_validate(payload)


class CommitteeReviewService:
    def __init__(self, client: CommitteeReviewClientProtocol) -> None:
        self._client = client

    def review_draft(self, draft: CommitteeDraftV1, context: dict) -> CommitteeReviewV1:
        payload = self._client.committee_review(draft.model_dump(), context)
        return CommitteeReviewV1.model_validate(payload)


class CommitteeFinalizeService:
    def __init__(self, client: CommitteeFinalizeClientProtocol) -> None:
        self._client = client

    def finalize(self, draft: CommitteeDraftV1, review: CommitteeReviewV1, context: dict) -> CommitteeResultV1:
        payload = self._client.committee_finalize(draft.model_dump(), review.model_dump(), context)
        return CommitteeResultV1.model_validate(payload)
