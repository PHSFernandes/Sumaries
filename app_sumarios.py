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

th.col-center { text-align: center; }

td {
    font-size: 8.5pt;
    padding: 4pt 7pt;
    border: 0.5pt solid #cbd5e1;
    vertical-align: middle;
    word-wrap: break-word;
}

tbody tr:nth-child(even) td { background-color: #f8fafc; }

td.col-uc { text-align: left; }
td.col-nowrap { text-align: center; white-space: nowrap; }
td.col-estado { text-align: center; }

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


def build_docente_pdf(
    df_doc: pd.DataFrame,
    docente: str,
    titulo_periodo: str,
    incluir_coluna_ano: bool,
) -> bytes:
    total_geral = len(df_doc)
    docente_esc = html.escape(docente.strip())
    docente_salutation = html.escape(format_docente_salutation(docente))

    courses_html = []
    cursos_presentes = [c for c in COURSE_ORDER if c in df_doc['Curso'].values]
    cursos_extras = sorted(set(df_doc['Curso'].unique()) - set(COURSE_ORDER))

    for curso in cursos_presentes + cursos_extras:
        df_c = df_doc[df_doc['Curso'] == curso].copy()
        sort_cols = ['Unidade Curricular/Turma', 'Ano', 'dt_sort', 'Hora'] if incluir_coluna_ano else [
            'Unidade Curricular/Turma', 'dt_sort', 'Hora'
        ]
        df_c = df_c.sort_values(by=sort_cols)

        rows_html = []
        for _, r in df_c.iterrows():
            uc = html.escape(str(r['Unidade Curricular/Turma']))
            ano_val = html.escape(str(r['Ano']))
            dt_oc = html.escape(str(r['Data_Fmt']))
            hr = html.escape(str(r['Hora']))
            est = html.escape(str(r['Estado']))

            if incluir_coluna_ano:
                rows_html.append(
                    f"<tr>"
                    f"<td class='col-uc' style='width: 46%;'>{uc}</td>"
                    f"<td class='col-nowrap' style='width: 10%;'>{ano_val}</td>"
                    f"<td class='col-nowrap' style='width: 12%;'>{dt_oc}</td>"
                    f"<td class='col-nowrap' style='width: 12%;'>{hr}</td>"
                    f"<td class='col-estado' style='width: 20%;'>{est}</td>"
                    f"</tr>"
                )
            else:
                rows_html.append(
                    f"<tr>"
                    f"<td class='col-uc' style='width: 52%;'>{uc}</td>"
                    f"<td class='col-nowrap' style='width: 13%;'>{dt_oc}</td>"
                    f"<td class='col-nowrap' style='width: 13%;'>{hr}</td>"
                    f"<td class='col-estado' style='width: 22%;'>{est}</td>"
                    f"</tr>"
                )

        colspan_val = 5 if incluir_coluna_ano else 4
        subtotal_label = f"Total {curso}: {len(df_c)} {'sumário' if len(df_c) == 1 else 'sumários'}"
        rows_html.append(
            f"<tr class='subtotal-row'>"
            f"<td colspan='{colspan_val}'>{html.escape(subtotal_label)}</td>"
            f"</tr>"
        )

        if incluir_coluna_ano:
            thead_html = """
                <tr>
                    <th style="width: 46%;">Unidade Curricular/Turma</th>
                    <th class="col-center" style="width: 10%;">Ano</th>
                    <th class="col-center" style="width: 12%;">Data Ocupação</th>
                    <th class="col-center" style="width: 12%;">Hora</th>
                    <th class="col-center" style="width: 20%;">Estado</th>
                </tr>
            """
        else:
            thead_html = """
                <tr>
                    <th style="width: 52%;">Unidade Curricular/Turma</th>
                    <th class="col-center" style="width: 13%;">Data Ocupação</th>
                    <th class="col-center" style="width: 13%;">Hora</th>
                    <th class="col-center" style="width: 22%;">Estado</th>
                </tr>
            """

        courses_html.append(f"""
        <div class="course-block">
            <div class="course-title">{html.escape(curso)}</div>
            <table>
                <thead>{thead_html}</thead>
                <tbody>{''.join(rows_html)}</tbody>
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
        <div class="header-title">SUMÁRIOS EM ATRASO - {html.escape(titulo_periodo)}</div>
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


def build_gerencial_pdf(ct: pd.DataFrame, titulo_periodo: str, cursos_presentes: list[str]) -> bytes:
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
        <div class="header-title">REPORT GERENCIAL — SUMÁRIOS EM ATRASO - {html.escape(titulo_periodo)}</div>
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


def prepare_filtered_data(df_all: pd.DataFrame, anos_alvo: list[str]) -> pd.DataFrame:
    sub = df_all[
        (df_all['Ano'].astype(str).str.strip().isin(anos_alvo))
        & (df_all['Estado'].astype(str).str.strip() != 'Lançado')
    ].copy()

    if sub.empty:
        return sub

    sub['Docente'] = sub['Docente'].astype(str).str.strip()
    sub['Estado'] = sub['Estado'].astype(str).str.strip()
    sub['Curso'] = sub['Curso'].astype(str).str.strip().str.upper()
    sub['Ano'] = sub['Ano'].astype(str).str.strip()
    sub['Hora'] = sub['Hora'].astype(str).str.strip()
    sub['Unidade Curricular/Turma'] = sub['Unidade Curricular/Turma'].astype(str).str.strip()

    sub['dt_sort'] = pd.to_datetime(sub['Data Ocupação'], dayfirst=True, errors='coerce')
    sub['Data_Fmt'] = sub['dt_sort'].dt.strftime('%d-%m-%Y').fillna(sub['Data Ocupação'].astype(str).str.strip())
    return sub


def generate_all_artifacts(
    sub: pd.DataFrame,
    anos_alvo: list[str],
    todos_anos: bool,
):
    if sub.empty:
        return None, None, {}, b"", ""

    anos_efetivos = sorted(sub['Ano'].unique().tolist())
    if todos_anos:
        titulo_periodo = f"TODOS OS ANOS ({' / '.join(anos_efetivos)})"
        tag_arquivo = "Todos_os_Anos"
        incluir_col_ano = len(anos_efetivos) > 1
    else:
        titulo_periodo = f"ANO {anos_alvo[0]}"
        tag_arquivo = anos_alvo[0]
        incluir_col_ano = False

    ct = pd.crosstab(sub['Docente'], sub['Estado'])
    for st_name in STATES_ORDER:
        if st_name not in ct.columns:
            ct[st_name] = 0
    ct = ct[STATES_ORDER].sort_index()
    ct['Total'] = ct.sum(axis=1)

    cursos_ordenados = [c for c in COURSE_ORDER if c in sub['Curso'].values] + sorted(
        set(sub['Curso'].unique()) - set(COURSE_ORDER)
    )
    gerencial_bytes = build_gerencial_pdf(ct, titulo_periodo, cursos_ordenados)

    individual_pdfs = {}
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for docente in sorted(sub['Docente'].unique()):
            df_doc = sub[sub['Docente'] == docente]
            pdf_bytes = build_docente_pdf(df_doc, docente, titulo_periodo, incluir_col_ano)
            fname = f"Sumarios_Atraso_{tag_arquivo}_{safe_filename(docente)}.pdf"
            individual_pdfs[docente] = (fname, pdf_bytes)
            zf.writestr(fname, pdf_bytes)

    return ct, gerencial_bytes, individual_pdfs, zip_buffer.getvalue(), tag_arquivo


def on_toggle_all_docentes(docentes_list: list[str]):
    estado_geral = st.session_state["cb_all_docentes"]
    for doc in docentes_list:
        st.session_state[f"cb_doc_{doc}"] = estado_geral


def on_toggle_single_docente(docentes_list: list[str]):
    st.session_state["cb_all_docentes"] = all(
        st.session_state.get(f"cb_doc_{doc}", True) for doc in docentes_list
    )


st.title("Reports de Sumários em Atraso")

uploaded_files = st.file_uploader(
    "Carregar ficheiros Excel por curso/ano (.xlsx)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.subheader("1. Configuração dos ficheiros carregados")
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

        st.divider()
        st.subheader("2. Período dos Reports")

        col_mode, col_year = st.columns([1.2, 1])
        with col_mode:
            modo_geracao = st.radio(
                "Modo de geração dos Reports",
                ["Separado por ano", "Todos os anos consolidados"],
                horizontal=True,
            )

        todos_anos_flag = modo_geracao == "Todos os anos consolidados"

        with col_year:
            if todos_anos_flag:
                anos_alvo = anos_presentes
                st.info(f"Anos incluídos: {', '.join(anos_presentes)}")
            else:
                default_ano_idx = anos_presentes.index("2025-26") if "2025-26" in anos_presentes else 0
                ano_escolhido = st.selectbox(
                    "Selecionar Ano Letivo",
                    anos_presentes,
                    index=default_ano_idx,
                )
                anos_alvo = [ano_escolhido]

        sub_periodo = prepare_filtered_data(df_consolidado, anos_alvo)

        if sub_periodo.empty:
            st.warning("Não existem sumários pendentes para o período selecionado.")
        else:
            contagem_por_docente = sub_periodo['Docente'].value_counts().to_dict()
            docentes_disponiveis = sorted(contagem_por_docente.keys())

            for doc in docentes_disponiveis:
                if f"cb_doc_{doc}" not in st.session_state:
                    st.session_state[f"cb_doc_{doc}"] = st.session_state.get("cb_all_docentes", True)

            st.session_state["cb_all_docentes"] = all(
                st.session_state.get(f"cb_doc_{doc}", True) for doc in docentes_disponiveis
            )

            st.divider()
            st.subheader(f"3. Seleção de Professores ({len(docentes_disponiveis)} encontrados)")

            with st.container(border=True):
                st.checkbox(
                    "Todos os professores (marcar / desmarcar lote)",
                    key="cb_all_docentes",
                    on_change=on_toggle_all_docentes,
                    args=(docentes_disponiveis,),
                )
                st.markdown("---")
                cols_doc = st.columns(2)
                for idx_d, doc in enumerate(docentes_disponiveis):
                    qtd = contagem_por_docente[doc]
                    with cols_doc[idx_d % 2]:
                        st.checkbox(
                            f"{doc} ({qtd})",
                            key=f"cb_doc_{doc}",
                            on_change=on_toggle_single_docente,
                            args=(docentes_disponiveis,),
                        )

            docentes_selecionados = [
                doc for doc in docentes_disponiveis if st.session_state.get(f"cb_doc_{doc}", True)
            ]

            if not docentes_selecionados:
                st.warning("Selecione pelo menos um docente nas checkboxes acima para gerar os relatórios.")
            else:
                sub_final = sub_periodo[sub_periodo['Docente'].isin(docentes_selecionados)].copy()

                with st.spinner("A gerar relatórios em PDF..."):
                    ct, gerencial_bytes, individual_pdfs, zip_bytes, tag_arq = generate_all_artifacts(
                        sub_final, anos_alvo, todos_anos_flag
                    )

                st.divider()
                st.subheader("4. Resumo e Downloads")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Professores Selecionados", f"{len(ct)} / {len(docentes_disponiveis)}")
                m2.metric("Total Sumários em Atraso", int(ct['Total'].sum()))
                m3.metric("Por Lançar", int(ct['Por Lançar'].sum()))
                expirados_total = int(
                    ct['Por Lançar (Expirado)'].sum()
                    + ct['Pré-lançado (Expirado)'].sum()
                    + ct['Faltou'].sum()
                )
                m4.metric("Expirados / Faltou", expirados_total)

                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        label=f"Baixar Report Gerencial (PDF — {len(ct)} docentes)",
                        data=gerencial_bytes,
                        file_name=f"Report_Gerencial_Sumarios_Atraso_{tag_arq}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary",
                    )
                with dl2:
                    st.download_button(
                        label=f"Baixar PDFs Individuais Selecionados (ZIP — {len(individual_pdfs)} ficheiros)",
                        data=zip_bytes,
                        file_name=f"Sumarios_em_Atraso_{tag_arq}_Por_Docente.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )

                st.markdown("**Pré-visualização — Quadro Gerencial (apenas professores marcados)**")
                st.dataframe(ct, use_container_width=True)

                with st.expander("Downloads individuais avulsos (opcional)"):
                    cols_ind = st.columns(2)
                    for idx_b, (doc_nome, (fname_ind, bytes_ind)) in enumerate(individual_pdfs.items()):
                        with cols_ind[idx_b % 2]:
                            st.download_button(
                                label=f"PDF — {doc_nome}",
                                data=bytes_ind,
                                file_name=fname_ind,
                                mime="application/pdf",
                                key=f"dl_ind_{doc_nome}",
                                use_container_width=True,
                            )
