import io
import re
import html
import zipfile
import unicodedata
import pandas as pd
import streamlit as st
import weasyprint

st.set_page_config(
    page_title="Sumários em Atraso - Coordenação",
    layout="wide",
)

COURSE_OPTIONS = ['MIMV', 'LCB', 'LEV', 'Outro...']
COURSE_ORDER = ['MIMV', 'LCB', 'LEV']
YEAR_OPTIONS = ['2024-25', '2025-26', '2026-27', '2027-28', 'Outro...']
STATES_ORDER = [
    'Por Lançar',
    'Por Lançar (Expirado)',
    'Pré-lançado (Expirado)',
    'Faltou',
]
LOWER_WORDS = {'de', 'da', 'do', 'dos', 'das', 'e'}


def format_docente_salutation(name_upper: str) -> str:
    parts = str(name_upper).strip().split()
    formatted = []
    for idx, p in enumerate(parts):
        low = p.lower()
        if idx > 0 and low in LOWER_WORDS:
            formatted.append(low)
        else:
            formatted.append(p.capitalize())
    return " ".join(formatted)


def safe_filename(name: str) -> str:
    nfkd = unicodedata.normalize('NFKD', str(name))
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'[^A-Za-z0-9]+', '_', ascii_str).strip('_')


def detect_course_from_filename(filename: str) -> str:
    upper = filename.upper()
    for c in COURSE_ORDER:
        if re.search(rf'(^|[^A-Z0-9]){c}([^A-Z0-9]|$)', upper):
            return c
    return 'MIMV'


def detect_year_from_filename(filename: str) -> str:
    match = re.search(r'(20\d{2}-\d{2})', filename)
    if match and match.group(1) in YEAR_OPTIONS:
        return match.group(1)
    return '2025-26'


CSS_DOCENTE = """
@page {
    size: A4 landscape;
    margin: 26mm 14mm 16mm 14mm;
    @top-left {
        content: element(docHeader);
        width: 100%;
    }
    @bottom-right {
        content: counter(page) "/" counter(pages);
        font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
        font-size: 9pt;
        color: #333333;
    }
}

* { box-sizing: border-box; }

body {
    font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
    font-size: 9pt;
    color: #1f2937;
    margin: 0;
    padding: 0;
}

.running-header {
    position: running(docHeader);
    width: 100%;
    border-bottom: 1.5px solid #1e3a5f;
    padding-bottom: 4pt;
    margin-bottom: 6pt;
}

.header-title {
    font-size: 12pt;
    font-weight: 700;
    color: #1e3a5f;
    letter-spacing: 0.3px;
    margin: 0 0 2pt 0;
}

.header-docente {
    font-size: 10.5pt;
    font-weight: 700;
    color: #111827;
    margin: 0;
}

.course-block { margin-bottom: 12pt; }

.course-title {
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    color: #1e3a5f;
    background-color: #eef2f7;
    border-left: 3.5px solid #1e3a5f;
    padding: 4pt 8pt;
    margin: 0 0 4pt 0;
    break-after: avoid;
    page-break-after: avoid;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 4pt;
    table-layout: fixed;
}

thead { display: table-header-group; }

tr {
    break-inside: avoid;
    page-break-inside: avoid;
}

th {
    background-color: #1e3a5f;
    color: #ffffff;
    font-weight: 700;
    font-size: 8.5pt;
    text-align: left;
    padding: 5pt 7pt;
    border: 0.6pt solid #1e3a5f;
}

th.col-data, th.col-hora, th.col-estado { text-align: center; }

td {
    font-size: 8.5pt;
    padding: 4pt 7pt;
    border: 0.5pt solid #cbd5e1;
    vertical-align: middle;
    word-wrap: break-word;
}

tbody tr:nth-child(even) td { background-color: #f8fafc; }

td.col-uc { width: 52%; text-align: left; }
td.col-data { width: 13%; text-align: center; white-space: nowrap; }
td.col-hora { width: 13%; text-align: center; white-space: nowrap; }
td.col-estado { width: 22%; text-align: center; }

tr.subtotal-row td {
    background-color: #e2e8f0 !important;
    font-weight: 700;
    color: #0f172a;
    border-top: 1pt solid #64748b;
    border-bottom: 1pt solid #64748b;
    padding: 4.5pt 7pt;
}

.grand-total {
    margin-top: 6pt;
    margin-bottom: 12pt;
    padding: 5pt 8pt;
    background-color: #f1f5f9;
    border: 0.8pt solid #94a3b8;
    font-weight: 700;
    font-size: 9.5pt;
    color: #0f172a;
    break-inside: avoid;
    page-break-inside: avoid;
}

.closing-note {
    margin-top: 10pt;
    padding: 8pt 10pt;
    border: 0.8pt solid #cbd5e1;
    background-color: #fafafa;
    font-size: 9pt;
    line-height: 1.45;
    color: #111827;
    break-inside: avoid;
    page-break-inside: avoid;
}

.closing-note p { margin: 0 0 4pt 0; }
.closing-note p:last-child { margin-bottom: 0; }
"""

CSS_GERENCIAL = """
@page {
    size: A4 portrait;
    margin: 22mm 12mm 15mm 12mm;
    @top-left {
        content: element(docHeader);
        width: 100%;
    }
    @bottom-right {
        content: counter(page) "/" counter(pages);
        font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
        font-size: 8.5pt;
        color: #333333;
    }
}

* { box-sizing: border-box; }

body {
    font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
    font-size: 8pt;
    color: #1f2937;
    margin: 0;
    padding: 0;
}

.running-header {
    position: running(docHeader);
    width: 100%;
    border-bottom: 1.5px solid #1e3a5f;
    padding-bottom: 4pt;
    margin-bottom: 6pt;
}

.header-title {
    font-size: 11.5pt;
    font-weight: 700;
    color: #1e3a5f;
    letter-spacing: 0.3px;
    margin: 0 0 2pt 0;
}

.header-subtitle {
    font-size: 9pt;
    font-weight: 600;
    color: #475569;
    margin: 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}

thead { display: table-header-group; }

tr {
    break-inside: avoid;
    page-break-inside: avoid;
}

th {
    background-color: #1e3a5f;
    color: #ffffff;
    font-weight: 700;
    font-size: 7.5pt;
    padding: 5pt 4pt;
    border: 0.6pt solid #1e3a5f;
    vertical-align: middle;
    line-height: 1.25;
}

th.col-docente { text-align: left; padding-left: 6pt; }
th.col-num, th.col-total, th.col-blank { text-align: center; }

td {
    font-size: 7.8pt;
    padding: 5.5pt 4pt;
    border: 0.5pt solid #cbd5e1;
    vertical-align: middle;
    word-wrap: break-word;
}

tbody tr:nth-child(even) td { background-color: #f8fafc; }

td.col-docente {
    text-align: left;
    padding-left: 6pt;
    font-weight: 500;
    color: #111827;
}

td.col-num { text-align: center; }
td.zero-val { color: #94a3b8; }
td.nonzero-val { font-weight: 600; color: #0f172a; }

td.col-total {
    text-align: center;
    font-weight: 700;
    color: #1e3a5f;
    background-color: #f1f5f9 !important;
}

td.col-blank { background-color: #ffffff !important; }

tr.total-row td {
    background-color: #e2e8f0 !important;
    font-weight: 700;
    font-size: 8pt;
    color: #0f172a;
    border-top: 1.2pt solid #475569;
    border-bottom: 1.2pt solid #475569;
    padding: 5.5pt 4pt;
}
"""


def build_docente_pdf(df_doc: pd.DataFrame, docente: str, ano_letivo: str) -> bytes:
    total_geral = len(df_doc)
    docente_esc = html.escape(docente.strip())
    docente_salutation = html.escape(format_docente_salutation(docente))

    courses_html = []
    cursos_presentes = [c for c in COURSE_ORDER if c in df_doc['Curso'].values]
    cursos_extras = sorted(set(df_doc['Curso'].unique()) - set(COURSE_ORDER))

    for curso in cursos_presentes + cursos_extras:
        df_c = df_doc[df_doc['Curso'] == curso].copy()
        df_c = df_c.sort_values(by=['Unidade Curricular/Turma', 'dt_sort', 'Hora'])

        rows_html = []
        for _, r in df_c.iterrows():
            uc = html.escape(str(r['Unidade Curricular/Turma']))
            dt_oc = html.escape(str(r['Data_Fmt']))
            hr = html.escape(str(r['Hora']))
            est = html.escape(str(r['Estado']))
            rows_html.append(
                f"<tr>"
                f"<td class='col-uc'>{uc}</td>"
                f"<td class='col-data'>{dt_oc}</td>"
                f"<td class='col-hora'>{hr}</td>"
                f"<td class='col-estado'>{est}</td>"
                f"</tr>"
            )

        subtotal_label = f"Total {curso}: {len(df_c)} {'sumário' if len(df_c) == 1 else 'sumários'}"
        rows_html.append(
            f"<tr class='subtotal-row'>"
            f"<td colspan='4'>{html.escape(subtotal_label)}</td>"
            f"</tr>"
        )

        courses_html.append(f"""
        <div class="course-block">
            <div class="course-title">{html.escape(curso)}</div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 52%;">Unidade Curricular/Turma</th>
                        <th class="col-data" style="width: 13%;">Data Ocupação</th>
                        <th class="col-hora" style="width: 13%;">Hora</th>
                        <th class="col-estado" style="width: 22%;">Estado</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        """)

    total_geral_text = (
        f"Total Geral: {total_geral} "
        f"{'sumário em atraso' if total_geral == 1 else 'sumários em atraso'}"
    )

    full_html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<style>{CSS_DOCENTE}</style>
</head>
<body>
    <div class="running-header">
        <div class="header-title">SUMÁRIOS EM ATRASO - ANO {html.escape(ano_letivo)}</div>
        <div class="header-docente">{docente_esc}</div>
    </div>

    {''.join(courses_html)}

    <div class="grand-total">{html.escape(total_geral_text)}</div>

    <div class="closing-note">
        <p>Estimado(a) Professor(a) {docente_salutation},</p>
        <p>Para os sumários que se encontram EXPIRADOS, será necessário marcar connosco um dia e uma hora para proceder à respetiva correção, utilizando o perfil de acesso da Coordenação do Curso, no computador disponível para esse efeito.</p>
        <p>Os sumários cujo estado seja “POR LANÇAR” são, em princípio, passíveis de serem resolvidos no Sec-Online, no próprio perfil do Professor. Caso os sumários no estado “POR LANÇAR” aqui listados já tenham sido resolvidos, por favor, desconsidere este relatório.</p>
    </div>
</body>
</html>
"""
    return weasyprint.HTML(string=full_html).write_pdf()


def build_gerencial_pdf(ct: pd.DataFrame, ano_letivo: str, cursos_presentes: list[str]) -> bytes:
    totals = ct.sum(axis=0)
    rows_html = []

    for docente, row in ct.iterrows():
        doc_esc = html.escape(str(docente))
        cells = [f"<td class='col-docente'>{doc_esc}</td>"]
        for st_name in STATES_ORDER:
            val = int(row[st_name])
            cls = "col-num zero-val" if val == 0 else "col-num nonzero-val"
            cells.append(f"<td class='{cls}'>{val}</td>")
        cells.append(f"<td class='col-total'>{int(row['Total'])}</td>")
        cells.append("<td class='col-blank'></td>")
        cells.append("<td class='col-blank'></td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    total_cells = [f"<td class='col-docente'>TOTAL GERAL ({len(ct)} Docentes)</td>"]
    for st_name in STATES_ORDER:
        total_cells.append(f"<td class='col-num'>{int(totals[st_name])}</td>")
    total_cells.append(f"<td class='col-num'>{int(totals['Total'])}</td>")
    total_cells.append("<td class='col-num'>—</td>")
    total_cells.append("<td class='col-num'>—</td>")
    rows_html.append(f"<tr class='total-row'>{''.join(total_cells)}</tr>")

    cursos_str = ", ".join(cursos_presentes)
    full_html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<style>{CSS_GERENCIAL}</style>
</head>
<body>
    <div class="running-header">
        <div class="header-title">REPORT GERENCIAL — SUMÁRIOS EM ATRASO - ANO {html.escape(ano_letivo)}</div>
        <div class="header-subtitle">Consolidado por Docente e Estado (Cursos: {html.escape(cursos_str)})</div>
    </div>

    <table>
        <thead>
            <tr>
                <th class="col-docente" style="width: 34%;">Docente</th>
                <th class="col-num" style="width: 9%;">Por<br>Lançar</th>
                <th class="col-num" style="width: 11%;">Por Lançar<br>(Expirado)</th>
                <th class="col-num" style="width: 11%;">Pré-lançado<br>(Expirado)</th>
                <th class="col-num" style="width: 7%;">Faltou</th>
                <th class="col-total" style="width: 8%;">Total</th>
                <th class="col-blank" style="width: 11%;">Data</th>
                <th class="col-blank" style="width: 9%;">Hora</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>
</body>
</html>
"""
    return weasyprint.HTML(string=full_html).write_pdf()


def generate_all_artifacts(df_all: pd.DataFrame, ano_letivo: str):
    sub = df_all[
        (df_all['Ano'].astype(str).str.strip() == str(ano_letivo).strip())
        & (df_all['Estado'].astype(str).str.strip() != 'Lançado')
    ].copy()

    if sub.empty:
        return None, None, {}, b""

    sub['Docente'] = sub['Docente'].astype(str).str.strip()
    sub['Estado'] = sub['Estado'].astype(str).str.strip()
    sub['Curso'] = sub['Curso'].astype(str).str.strip().str.upper()
    sub['Hora'] = sub['Hora'].astype(str).str.strip()
    sub['Unidade Curricular/Turma'] = sub['Unidade Curricular/Turma'].astype(str).str.strip()

    sub['dt_sort'] = pd.to_datetime(sub['Data Ocupação'], dayfirst=True, errors='coerce')
    sub['Data_Fmt'] = sub['dt_sort'].dt.strftime('%d-%m-%Y').fillna(sub['Data Ocupação'].astype(str).str.strip())

    ct = pd.crosstab(sub['Docente'], sub['Estado'])
    for st_name in STATES_ORDER:
        if st_name not in ct.columns:
            ct[st_name] = 0
    ct = ct[STATES_ORDER].sort_index()
    ct['Total'] = ct.sum(axis=1)

    cursos_ordenados = [c for c in COURSE_ORDER if c in sub['Curso'].values] + sorted(
        set(sub['Curso'].unique()) - set(COURSE_ORDER)
    )
    gerencial_bytes = build_gerencial_pdf(ct, ano_letivo, cursos_ordenados)

    individual_pdfs = {}
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for docente in sorted(sub['Docente'].unique()):
            df_doc = sub[sub['Docente'] == docente]
            pdf_bytes = build_docente_pdf(df_doc, docente, ano_letivo)
            fname = f"Sumarios_Atraso_{ano_letivo}_{safe_filename(docente)}.pdf"
            individual_pdfs[docente] = (fname, pdf_bytes)
            zf.writestr(fname, pdf_bytes)

    return ct, gerencial_bytes, individual_pdfs, zip_buffer.getvalue()


st.title("Reports de Sumários em Atraso")

uploaded_files = st.file_uploader(
    "Carregar ficheiros Excel por curso/ano (.xlsx)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.subheader("Configuração dos ficheiros carregados")
    dfs_list = []

    for idx, up_file in enumerate(uploaded_files):
        file_bytes = up_file.getvalue()
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        default_sheet_idx = xls.sheet_names.index("Planilha1") if "Planilha1" in xls.sheet_names else 0

        detected_course = detect_course_from_filename(up_file.name)
        detected_year = detect_year_from_filename(up_file.name)

        with st.container(border=True):
            st.markdown(f"**Ficheiro {idx + 1}:** `{up_file.name}`")
            c1, c2, c3 = st.columns([1.2, 1, 1])

            with c1:
                sheet_sel = st.selectbox(
                    "Aba",
                    xls.sheet_names,
                    index=default_sheet_idx,
                    key=f"sheet_{idx}_{up_file.name}",
                )

            with c2:
                curso_choice = st.selectbox(
                    "Curso",
                    COURSE_OPTIONS,
                    index=COURSE_OPTIONS.index(detected_course),
                    key=f"curso_{idx}_{up_file.name}",
                )
                if curso_choice == 'Outro...':
                    curso_val = st.text_input(
                        "Sigla do Curso",
                        value="",
                        key=f"curso_custom_{idx}_{up_file.name}",
                    ).strip().upper()
                else:
                    curso_val = curso_choice

            with c3:
                ano_choice = st.selectbox(
                    "Ano Letivo",
                    YEAR_OPTIONS,
                    index=YEAR_OPTIONS.index(detected_year),
                    key=f"ano_{idx}_{up_file.name}",
                )
                if ano_choice == 'Outro...':
                    ano_val = st.text_input(
                        "Ano (ex: 2027-28)",
                        value="",
                        key=f"ano_custom_{idx}_{up_file.name}",
                    ).strip()
                else:
                    ano_val = ano_choice

        if curso_val and ano_val:
            df_part = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_sel)
            df_part['Curso'] = curso_val
            df_part['Ano'] = ano_val
            dfs_list.append(df_part)

    if dfs_list:
        df_consolidado = pd.concat(dfs_list, ignore_index=True)
        anos_presentes = sorted(df_consolidado['Ano'].dropna().astype(str).unique().tolist())
        default_ano_report_idx = anos_presentes.index("2025-26") if "2025-26" in anos_presentes else 0

        st.divider()
        ano_report = st.selectbox(
            "Ano Letivo para geração dos Reports",
            anos_presentes,
            index=default_ano_report_idx,
        )

        with st.spinner("A gerar relatórios em PDF..."):
            ct, gerencial_bytes, individual_pdfs, zip_bytes = generate_all_artifacts(
                df_consolidado, ano_report
            )

        if ct is None:
            st.warning(f"Não existem sumários pendentes para o ano {ano_report}.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Docentes com Pendências", len(ct))
            m2.metric("Total Sumários em Atraso", int(ct['Total'].sum()))
            m3.metric("Por Lançar", int(ct['Por Lançar'].sum()))
            expirados_total = int(
                ct['Por Lançar (Expirado)'].sum()
                + ct['Pré-lançado (Expirado)'].sum()
                + ct['Faltou'].sum()
            )
            m4.metric("Expirados / Faltou", expirados_total)

            st.divider()

            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    label=f"Baixar Report Gerencial (PDF — {len(ct)} docentes)",
                    data=gerencial_bytes,
                    file_name=f"Report_Gerencial_Sumarios_Atraso_{ano_report}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
            with dl2:
                st.download_button(
                    label=f"Baixar Todos os PDFs por Docente (ZIP — {len(individual_pdfs)} ficheiros)",
                    data=zip_bytes,
                    file_name=f"Sumarios_em_Atraso_{ano_report}_Por_Docente.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

            st.subheader("Pré-visualização — Quadro Gerencial")
            st.dataframe(ct, use_container_width=True)

            st.subheader("Download Individual por Docente")
            doc_escolhido = st.selectbox("Selecionar docente", list(individual_pdfs.keys()))
            if doc_escolhido:
                fname_ind, bytes_ind = individual_pdfs[doc_escolhido]
                st.download_button(
                    label=f"Baixar PDF — {doc_escolhido}",
                    data=bytes_ind,
                    file_name=fname_ind,
                    mime="application/pdf",
                )
