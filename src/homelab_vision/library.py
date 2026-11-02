"""Combine selected document and video results without pretending their scores match."""
from pathlib import Path
from .document_app import search_document
from .video_analysis import search_frames


def search_library(query: str, documents: list[Path], videos: list[Path], top_k: int = 10) -> dict:
    if not query.strip() or len(query)>2000 or not 1<=top_k<=20 or not 1<=len(documents)+len(videos)<=20:
        raise ValueError('Select 1 to 20 indexes, a nonempty query up to 2000 characters, and top-k 1 to 20')
    if len({p.resolve() for p in documents+videos})!=len(documents)+len(videos):
        raise ValueError('Do not supply the same index twice')
    hits=[];sources=[]
    for kind,paths in [('document',documents),('video',videos)]:
        for number,path in enumerate(paths,1):
            source_id=f'{kind}-{number}'
            result=search_document(path,query,top_k) if kind=='document' else search_frames(path,query)
            sources.append(dict(id=source_id,kind=kind,state=result['state'],returned_hits=len(result['hits'])))
            for rank,hit in enumerate(result['hits'][:top_k],1):
                hits.append(dict(source_id=source_id,kind=kind,within_source_rank=rank,rank_weight=1/(60+rank),evidence=hit))
    # This is equal-source rank interleaving, not semantic fusion or calibrated relevance.
    hits.sort(key=lambda h:(-h['rank_weight'],h['source_id']))
    return dict(state='review_required' if hits else 'not_found',query=query,sources=sources,hits=hits[:top_k],
        ranking='Equal-source rank interleaving using 1/(60+rank); ties use source ID. Raw BM25 and video token-coverage scores are not compared.',
        notice='Only explicitly selected indexes are searched. Page citations and video timestamps retain their different meanings. These are excerpts and model proposals, not a generated cross-source answer.')
