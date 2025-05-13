import snapatac2 as snap
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from scipy.sparse import csr_matrix  
from sklearn.metrics import (
    adjusted_rand_score,
    normalized_mutual_info_score,
)
import scib
import numpy as np
import scanpy as sc


def plot_umap_raw(
    adata,
    umap_files,
    n_features=50_000,
    key="X",
    layer_key="counts",
    celltype_key="cell_type",
    umap_key="X_umap",
    seed=42,
    width=1280,
    height=1280,
):
    leiden_key = f"{key}_leiden"
    # celltype_key = "batch_id"
    # use copied raw counts layer
    adata.X = adata.layers[layer_key].copy()
    if not isinstance(adata.X, csr_matrix):
        adata.X = csr_matrix(adata.X)
    # preprocess
    snap.pp.select_features(adata, n_features=None)
    snap.tl.spectral(adata)
    snap.tl.umap(adata, use_rep="X_spectral", key_added="umap")
    snap.pp.knn(adata, use_rep="X_spectral")
    snap.tl.leiden(adata, key_added=leiden_key)
    # plot single umap & return
    for umap_file in umap_files:
        umap_fig = sc.pl.umap(
            adata,
            color=[celltype_key],
            title="raw_counts",
            return_fig=True,
            show=False,
        )
# save umap
    umap_fig.savefig(umap_files[0], bbox_inches="tight")
    if celltype_key =="batch_id":
        snap.pp.select_features(adata, n_features=5000)
        print(adata[:,adata.var["selected"]].X.toarray().astype('float32'))
        adata.obsm["hvg"] = adata[:,adata.var["selected"]].X.toarray().astype('float32')
        metrics = eval_scib_metrics(adata,batch_key="batch_id",  label_key = "cell_type",umap_key="hvg")
        snap.tl.umap(adata, use_rep="hvg", key_added="umap")
        umap_fig = sc.pl.umap(
            adata,
            color=[celltype_key],
            title="raw_counts",
            return_fig=True,
            show=False,
        )
# save umap
        umap_fig.savefig(umap_files[0], bbox_inches="tight")

    else:
        metrics = kmeans_umap(
            adata, umap_key=umap_key, celltype_key=celltype_key, seed=seed
        )
    # return values
    return metrics




def plot_umap_embed(
    adata,
    umap_files,
    ax,
    umap_title=None,
    n_neighbors=30,
    key="cellstory_atac",
    celltype_key="cell_type",
    umap_key="X_umap",
    seed=42,
):  
    if celltype_key =="batch_id":
        metrics = eval_scib_metrics(adata,batch_key="batch_id",  label_key = "cell_type",umap_key = key)
    
    rep_key = key
    neighbors_key = f"{key}_neighbors"
    leiden_key = f"{key}_leiden"
    sc.pp.neighbors(adata, n_neighbors=30, use_rep=rep_key, key_added=neighbors_key)
    sc.tl.leiden(adata, key_added=leiden_key, neighbors_key=neighbors_key)
    sc.tl.umap(adata, neighbors_key=neighbors_key)
    # plot single umap & return
    # celltype_key = "batch_id"
    umap_fig = sc.pl.umap(
            adata,
            color=[celltype_key],
            title=umap_title,
            neighbors_key=neighbors_key,
            return_fig=True,
            show=False,
        )
    # save umap
    umap_fig.savefig(umap_files[0], bbox_inches="tight")
    # plot on ax
    sc.pl.umap(
        adata,
        color=[celltype_key],
        title=umap_title,
        neighbors_key=neighbors_key,
        return_fig=False,
        show=False,
        ax=ax,
    )
    if celltype_key != "batch_id":
        metrics = kmeans_umap(
            adata, umap_key=umap_key, celltype_key=celltype_key, seed=seed
        )
    
    # return values
    return metrics
def eval_scib_metrics(
    adata,
    batch_key = "batch_id",
    label_key = "cell_type",
    umap_key="cellstory_atac",
    notes = None,
):
    
    adata.X = adata.X.astype('float32')
    results = scib.metrics.metrics(
        adata,
        adata_int=adata,
        batch_key=batch_key,
        label_key=label_key,
        embed=umap_key,
        isolated_labels_asw_=False,
        silhouette_=True,
        hvg_score_=False,
        graph_conn_=True,
        pcr_=True,
        isolated_labels_f1_=False,
        trajectory_=False,
        nmi_=True,  # use the clustering, bias to the best matching
        ari_=True,  # use the clustering, bias to the best matching
        cell_cycle_=False,
        kBET_=False,  # kBET return nan sometimes, need to examine
        ilisi_=False,
        clisi_=False,
    )

    result_dict = results[0].to_dict()
    result_dict["avg_bio"] = np.mean(
        [
            result_dict["NMI_cluster/label"],
            result_dict["ARI_cluster/label"],
            result_dict["ASW_label"],
        ]
    )

    # remove nan value in result_dict
    result_dict = {k: v for k, v in result_dict.items() if not np.isnan(v)}

    return result_dict
def kmeans_umap(adata, umap_key="X_umap", celltype_key="cell_type", seed=42):
    n_clusters = adata.obs[celltype_key].nunique()
    # 使用 K-means 聚类对 UMAP 结果进行聚类
    kmeans = KMeans(n_clusters=n_clusters, random_state=seed)  # 假设有10个聚类
    labels_pred = kmeans.fit_predict(adata.obsm[umap_key])

    # 计算和打印聚类指标
    labels_true = adata.obs[celltype_key]
    # silhouette = silhouette_score(adata.obsm[umap_key], labels_pred, metric="euclidean")
    ari = adjusted_rand_score(labels_true, labels_pred)
    nmi = normalized_mutual_info_score(labels_true, labels_pred)

    metrics = {"ARI": ari, "NMI": nmi}
    return metrics


def generate_atac_metrics(args, inferred_adata):
    atac_h5ad_stem = args.atac_h5ad.stem
    embed_h5ad = args.dirpath / f"{atac_h5ad_stem}.{args.obsm_key}.h5ad"
    raw_umap_png = args.dirpath / f"{atac_h5ad_stem}.umap.raw.png"
    raw_umap_html = args.dirpath / f"{atac_h5ad_stem}.umap.raw.html"
    raw_umap_files = [str(raw_umap_png), str(raw_umap_html)]
    embed_umap_png = args.dirpath / f"{atac_h5ad_stem}.umap.{args.obsm_key}.png"
    embed_umap_html = args.dirpath / f"{atac_h5ad_stem}.umap.{args.obsm_key}.html"
    embed_umap_files = [str(embed_umap_png), str(embed_umap_html)]
    umap_metric_tsv = args.dirpath / f"{atac_h5ad_stem}.umap.metrics.tsv"
    fig, ((embed_ax, raw_ax)) = plt.subplots(
        2, 1, figsize=(6.4, 9.6), gridspec_kw=dict(wspace=0.5)
    )
    # embedding umap
    celltype_key= "cell_type"
    if args.cell_type_annotation:
        celltype_key= "cell_type"
    if args.batch_correction:
        celltype_key= "batch_id"


    embed_metrics = plot_umap_embed(
        inferred_adata,
        umap_files=embed_umap_files,
        ax = embed_ax,
        key="cellstory_atac",
        celltype_key=celltype_key,
        umap_key="X_umap",
        seed=args.seed,
    )


    # raw counts umap
    raw_metrics = plot_umap_raw(
        inferred_adata,
        umap_files=raw_umap_files,
        n_features=50_000,
        key="X",
        layer_key="counts",
        celltype_key=celltype_key,
        umap_key="X_umap",
        seed=args.seed,
    )
    # save metric df
    metric_df = pd.DataFrame(
        [raw_metrics, embed_metrics], index=["raw_counts", f"{args.obsm_key}"]
    )
    metric_df.to_csv(umap_metric_tsv, sep="\t")
    # write extracted h5ad
    inferred_adata.write_h5ad(str(embed_h5ad))
    return metric_df


def generate_atac_cluster(args, inferred_adata):
    atac_h5ad_stem = args.atac_h5ad.stem
    embed_h5ad = args.dirpath / f"{atac_h5ad_stem}.{args.obsm_key}.h5ad"
    umap_files= args.dirpath / f"{atac_h5ad_stem}.{args.obsm_key}.png"
    key= "cellstory_atac"
    rep_key = key
    neighbors_key = f"{key}_neighbors"
    leiden_key = f"{key}_leiden"
    snap.tl.spectral(inferred_adata,features=None)

    snap.tl.umap(inferred_adata, use_rep="X_spectral", key_added="umap")
    snap.pp.knn(inferred_adata)
    snap.tl.leiden(inferred_adata)

    sc.pp.neighbors(inferred_adata, n_neighbors=30, use_rep=rep_key, key_added=neighbors_key)
    sc.tl.leiden(inferred_adata, key_added=leiden_key, neighbors_key=neighbors_key)
    sc.tl.umap(inferred_adata, neighbors_key=neighbors_key)
    # plot single umap & return
    
    umap_fig = sc.pl.umap(
            inferred_adata,
            color=["leiden"],
            title=None,
            neighbors_key=neighbors_key,
            return_fig=True,
            show=False,
        )
    # save umap
    umap_fig.savefig(umap_files, bbox_inches="tight")

    
   

    # write extracted h5ad
    inferred_adata.write_h5ad(str(embed_h5ad))
    return inferred_adata
