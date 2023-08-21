from ..model import SparsEmbed

__all__ = ["evaluate", "load_beir"]


def load_beir(dataset_name: str, split: str = "test") -> tuple[list, list, dict]:
    """Load BEIR dataset.

    Parameters
    ----------
    dataset_name
        Dataset name: scifact.

    """
    from beir import util
    from beir.datasets.data_loader import GenericDataLoader

    data_path = util.download_and_unzip(
        f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset_name}.zip",
        "./evaluation_datasets/",
    )

    documents, queries, qrels = GenericDataLoader(data_folder=data_path).load(
        split=split
    )

    documents = [
        {
            "id": document_id,
            "title": document["title"],
            "text": document["text"],
        }
        for document_id, document in documents.items()
    ]

    return documents, queries, qrels


def evaluate(
    retriever: SparsEmbed,
    batch_size: int,
    qrels: dict,
    queries: list[str],
    k: int = 30,
    metrics: list = [],
) -> dict:
    """Evaluation.

    Parameters
    ----------
    retriever
        Retriever.
    batch_size
        Batch size.
    qrels
        Qrels.
    queries
        Queries.
    k
        Number of documents to retrieve.
    metrics
        Metrics to compute.

    >>> from transformers import AutoModelForMaskedLM, AutoTokenizer
    >>> from sparsembed import model, retrieve, utils

    >>> device = "cpu"

    >>> model = model.Splade(
    ...     model=AutoModelForMaskedLM.from_pretrained("distilbert-base-uncased").to(device),
    ...     tokenizer=AutoTokenizer.from_pretrained("distilbert-base-uncased"),
    ...     device=device,
    ... )

    >>> documents, queries, qrels = utils.load_beir("scifact", split="test")

    >>> documents = documents[:10]

    >>> retriever = retrieve.SpladeRetriever(
    ...     key="id",
    ...     on=["title", "text"],
    ...     model=model
    ... )

    >>> retriever = retriever.add(
    ...     documents=documents,
    ...     batch_size=1
    ... )

    >>> utils.evaluate(
    ...     retriever=retriever,
    ...     batch_size=1,
    ...     qrels=qrels,
    ...     queries=queries,
    ...     k=30,
    ...     metrics=["map", "ndcg@10", "ndcg@100", "recall@10", "recall@100"]
    ... )

    """
    from ranx import Qrels, Run, evaluate

    qrels = Qrels(qrels)

    matchs = retriever(
        q=list(queries.values()),
        k=30,
        batch_size=batch_size,
    )

    run_dict = {
        id_query: {
            match["id"]: 1 - (rank / k) for rank, match in enumerate(query_matchs)
        }
        for id_query, query_matchs in zip(queries, matchs)
    }

    run = Run(run_dict)

    if not metrics:
        metrics = ["ndcg@10"] + [f"hits@{k}" for k in [1, 2, 3, 4, 5, 10]]

    return evaluate(
        qrels,
        run,
        metrics,
        make_comparable=True,
    )
