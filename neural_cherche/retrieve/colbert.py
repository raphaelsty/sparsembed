import torch
import tqdm

from .. import models, utils
from ..rank import ColBERT as ColBERTRanker

__all__ = ["ColBERT"]


class ColBERT(ColBERTRanker):
    """ColBERT retriever.

    Parameters
    ----------
    key
        Document unique identifier.
    on
        Document texts.
    model
        ColBERT model.

    Examples
    --------
    >>> from neural_cherche import models, retrieve
    >>> from pprint import pprint
    >>> import torch

    >>> _ = torch.manual_seed(42)

    >>> encoder = models.ColBERT(
    ...     model_name_or_path="sentence-transformers/all-mpnet-base-v2",
    ...     device="mps",
    ... )

    >>> documents = [
    ...     {"id": 0, "document": "Food"},
    ...     {"id": 1, "document": "Sports"},
    ...     {"id": 2, "document": "Cinema"},
    ... ]

    >>> queries = ["Food", "Sports", "Cinema"]

    >>> retriever = retrieve.ColBERT(
    ...    key="id",
    ...    on=["document"],
    ...    model=encoder,
    ... )

    >>> documents_embeddings = retriever.encode_documents(
    ...     documents=documents,
    ...     batch_size=3,
    ... )

    >>> retriever = retriever.add(
    ...     documents_embeddings=documents_embeddings,
    ... )

    >>> queries_embeddings = retriever.encode_queries(
    ...     queries=queries,
    ...     batch_size=3,
    ... )

    >>> scores = retriever(
    ...     queries_embeddings=queries_embeddings,
    ...     batch_size=3,
    ...     tqdm_bar=True,
    ...     k=3,
    ... )

    >>> pprint(scores)
    [[{'id': 0, 'similarity': 20.23601531982422},
      {'id': 2, 'similarity': 7.255690574645996},
      {'id': 1, 'similarity': 6.666046142578125}],
     [{'id': 1, 'similarity': 21.373430252075195},
      {'id': 2, 'similarity': 5.494492053985596},
      {'id': 0, 'similarity': 4.814355850219727}],
     [{'id': 1, 'similarity': 9.25660228729248},
      {'id': 0, 'similarity': 8.206350326538086},
      {'id': 2, 'similarity': 5.496612548828125}]]

    """

    def __init__(
        self,
        key: str,
        on: list[str],
        model: models.ColBERT,
    ) -> None:
        self.key = key
        self.on = on if isinstance(on, list) else [on]
        self.model = model
        self.device = self.model.device
        self.documents = []
        self.documents_embeddings = {}

    def add(
        self,
        documents_embeddings: dict[str, torch.Tensor],
    ) -> "ColBERT":
        """Add documents embeddings.

        Parameters
        ----------
        documents_embeddings
            Documents embeddings.
        documents
            Documents.
        """
        for document_key, tokens_embeddings in documents_embeddings.items():
            if document_key not in self.documents_embeddings:
                self.documents.append({self.key: document_key})
                self.documents_embeddings[document_key] = tokens_embeddings
        return self

    def __call__(
        self,
        queries_embeddings: dict[str, torch.Tensor],
        batch_size: int = 32,
        tqdm_bar: bool = True,
        k: int = None,
    ) -> list[list[str]]:
        """Rank documents  givent queries.

        Parameters
        ----------
        queries
            Queries.
        documents
            Documents.
        queries_embeddings
            Queries embeddings.
        documents_embeddings
            Documents embeddings.
        batch_size
            Batch size.
        tqdm_bar
            Show tqdm bar.
        k
            Number of documents to retrieve.
        """
        scores = []

        bar = (
            tqdm.tqdm(iterable=queries_embeddings.items(), position=0)
            if tqdm_bar
            else queries_embeddings.items()
        )

        for query, query_embedding in bar:
            query_scores = []

            embedding_query = torch.tensor(
                data=query_embedding,
                device=self.device,
                dtype=torch.float32,
            )

            for batch_query_documents in utils.batchify(
                X=self.documents,
                batch_size=batch_size,
                tqdm_bar=False,
            ):
                embeddings_batch_documents = torch.stack(
                    tensors=[
                        torch.tensor(
                            data=self.documents_embeddings[document[self.key]],
                            device=self.device,
                            dtype=torch.float32,
                        )
                        for document in batch_query_documents
                    ],
                    dim=0,
                )

                query_documents_scores = torch.einsum(
                    "sh,bth->bst",
                    embedding_query,
                    embeddings_batch_documents,
                )

                query_scores.append(
                    query_documents_scores.max(dim=2).values.sum(axis=1)
                )

            scores.append(torch.cat(tensors=query_scores, dim=0))

        return self._rank(scores=scores, documents=self.documents, k=k)

    def _rank(
        self, scores: torch.Tensor, documents: list[list[dict]], k: int
    ) -> list[list[dict]]:
        """Rank documents by scores.

        Parameters
        ----------
        scores
            Scores.
        documents
            Documents.
        k
            Number of documents to retrieve.
        """
        ranked = []

        for query_scores in scores:
            top_k = torch.topk(
                input=query_scores,
                k=min(k, len(documents)) if k is not None else len(documents),
                dim=-1,
            )

            ranked.append(
                [
                    {**documents[indice], "similarity": similarity}
                    for indice, similarity in zip(top_k.indices, top_k.values.tolist())
                ]
            )

        return ranked