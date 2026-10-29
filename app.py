import hashlib
import pandas as pd
import streamlit as st
from core import read_zip, matches, collisions, convert
st.set_page_config(page_title='FEC + pièces • Pennylane',page_icon='📎',layout='wide')
st.title('📎 FEC + pièces jointes')
st.caption('Déposez votre export comptable ZIP. Vérifiez les comptes, puis téléchargez le FEC et les PDF associés.')
st.caption('Libellé d’écriture : nom du client sur toutes les lignes de chaque facture ou avoir, y compris produits et TVA.')
upload=st.file_uploader('Export ZIP contenant le CSV comptable ou le FEC et les PDF',type=['zip'])
if not upload:
    st.info('Compatible avec le format de votre export fourni : CSV comptable + factures PDF, ou FEC à en-têtes + PDF. Un seul fichier comptable est lu pour éviter les doublons CSV / XLSX / TXT.')
    st.stop()
try:candidates,pdfs=read_zip(upload.getvalue())
except Exception as e:
    st.error(str(e));st.stop()
names=sorted(candidates,key=lambda n:(not n.lower().endswith('.csv'),n))
source=st.selectbox('Fichier comptable à utiliser (une seule source)',names)
digest=hashlib.sha256(upload.getvalue()+source.encode()).hexdigest()[:12]
raw=candidates[source]
a,b,c=st.columns(3)
a.metric('Lignes source',len(raw));b.metric('Références de pièces',raw.PieceRef.nunique());c.metric('PDF disponibles',len(pdfs))
st.subheader('Paramètres et corrections')
journal=st.text_input('Journal de destination','VT',help='VT proposé pour cet export de ventes. Toutes les écritures seront affectées à ce journal.')
with st.expander('Corriger les comptes auxiliaires par client',expanded=bool(collisions(raw))):
    clients=raw[raw.CompAuxNum.ne('')][['CompAuxNum','CompAuxLib']].drop_duplicates().reset_index(drop=True)
    clients['Compte_cible']=clients.CompAuxNum
    edited=st.data_editor(clients,disabled=['CompAuxNum','CompAuxLib'],hide_index=True,key='clients_'+digest)
    lookup={(r.CompAuxNum,r.CompAuxLib):r.Compte_cible for r in edited.itertuples()}
    raw=raw.copy()
    raw['CompAuxNum']=[lookup.get((r.CompAuxNum,r.CompAuxLib),r.CompAuxNum) for r in raw.itertuples()]
    st.caption('Utilisez les numéros existants du dossier Pennylane. Les modifications sont appliquées à toutes les lignes du client concerné.')
with st.expander('Voir / modifier les écritures'):
    df=st.data_editor(raw,num_rows='dynamic',hide_index=True,key='lines_'+digest)
    st.caption('Les dates et montants sont conservés. Aucun écart n’est compensé automatiquement. Les comptes de TVA restent ceux de la source.')
col=collisions(df)
accept=False
if col:
    st.warning('Un compte auxiliaire correspond à plusieurs noms. Corrigez-le ci-dessus ou confirmez ce regroupement.')
    st.dataframe(pd.DataFrame(col),hide_index=True)
    accept=st.checkbox('Je confirme que ces noms doivent être regroupés sur les mêmes comptes auxiliaires.')
with st.expander('Association des PDF',expanded=False):
    links=st.data_editor(matches(df,pdfs),disabled=['PieceRef'],column_config={'PDF':st.column_config.SelectboxColumn('PDF',options=['']+list(pdfs))},hide_index=True,key='pdf_'+digest)
result=convert(df,pdfs,links,journal.strip(),accept)
st.subheader('Téléchargement')
if not result['issues'].empty:
    st.error('Export bloqué : corrigez les anomalies ci-dessous. Aucune ligne n’est exclue silencieusement.')
    st.dataframe(result['issues'],hide_index=True)
    st.download_button('Télécharger les anomalies',result['issues'].to_csv(index=False,sep=';').encode('utf-8-sig'),'A_VERIFIER.csv','text/csv')
else:
    st.success(f"Contrôles réussis : {len(result['df'])} lignes, {len(result['control'])} écritures équilibrées avec PDF.")
    st.download_button('⬇ Télécharger FEC + pièces jointes',result['bundle'],'PENNYLANE_FEC_ET_PJ.zip','application/zip',type='primary')
    a,b=st.columns(2)
    a.download_button('FEC seul',result['fec'],'FEC_IMPORT.txt','text/plain')
    b.download_button('Archive PDF seule',result['pj'],'PIECES_JOINTES.zip','application/zip')
    if result['unused']:st.warning('PDF non utilisés : '+', '.join(result['unused']))
    with st.expander('Contrôle des associations'):st.dataframe(result['control'],hide_index=True)
st.info('Dans Pennylane : importer le fichier FEC_IMPORT.txt, puis cliquer sur le trombone « Joindre une archive » de cet import et sélectionner PIECES_JOINTES.zip. Le ZIP global sert uniquement au téléchargement.')
st.caption('Vérifiez les correspondances des comptes et journaux dans Pennylane. L’application ne consulte pas le dossier : elle ne peut détecter les écritures déjà présentes ni les comptes réservés. Export partiel au format FEC, non destiné au dépôt fiscal annuel. Les données ne sont pas enregistrées sur disque par l’application.')
st.link_button('Documentation officielle Pennylane','https://help.pennylane.com/fr/articles/18792-importer-un-fec')
