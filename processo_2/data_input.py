import os
import json
import random
import pandas as pd
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

NUM_PROPOSTAS = 40
OUTPUT_DIR = "processo_2/synthetic_proposals"

pesquisadores = [
    {
        "nome": "Ana Lopes da Silva", "cpf": "111.111.111-11", "siape": "1122334", "unidade_lotacao": "FACOM", 
        "titulacao": "Doutor", "pq": True, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.1001.2023", "titulo": "Modelagem de Sistemas Dinâmicos", "papel": "Coordenador", "vigencia_fim": "2026-12-31"},
            {"id_sigproj": "SIG.1050.2024", "titulo": "Otimização de Compiladores", "papel": "Colaborador", "vigencia_fim": "2025-08-30"}
        ]
    }, 
    {
        "nome": "Matheus Augusto Cintra", "cpf": "222.222.222-22", "siape": "2233445", "unidade_lotacao": "INISA", 
        "titulacao": "Doutor", "pq": False, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.2005.2023", "titulo": "Arquitetura de Banco de Dados Distribuídos", "papel": "Coordenador", "vigencia_fim": "2025-10-15"}
        ]
    }, 
    {
        "nome": "Carlos Alberto Shinaider", "cpf": "333.333.333-33", "siape": "3344556", "unidade_lotacao": "FACOM", 
        "titulacao": "Doutor", "pq": True, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.3010.2022", "titulo": "Visão Computacional Aplicada", "papel": "Coordenador", "vigencia_fim": "2026-03-01"}
        ]
    },
    {
        "nome": "Alice Wesner Flores", "cpf": "444.444.444-44", "siape": "4455667", "unidade_lotacao": "FAMEZ", 
        "titulacao": "Doutor", "pq": False, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.4022.2024", "titulo": "Análise de Dados Estruturados", "papel": "Coordenador", "vigencia_fim": "2026-06-30"}
        ]
    },
    {
        "nome": "Bruno Pereira Pontes", "cpf": "555.555.555-55", "siape": "5566778", "unidade_lotacao": "FACOM", 
        "titulacao": "Mestre", "pq": False, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.5033.2023", "titulo": "Desenvolvimento Web Fullstack", "papel": "Coordenador", "vigencia_fim": "2025-11-20"}
        ]
    }, 
    {
        "nome": "Fernanda Costa Poganski", "cpf": "666.666.666-66", "siape": "6677889", "unidade_lotacao": "FACOM", 
        "titulacao": "Doutor", "pq": False, 
        "pendencias": [
            {"id_pendencia": "PEND-2024-089", "tipo": "Relatório Final", "descricao": "Relatório Final PIBIC 2024/2025 em atraso", "data_vencimento": "2025-08-30", "impeditiva": True},
            {"id_pendencia": "PEND-2023-112", "tipo": "Prestação de Contas", "descricao": "Prestação de contas do edital 15/2023 pendente", "data_vencimento": "2024-01-15", "impeditiva": True}
        ], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.6044.2024", "titulo": "Redes de Sensores Sem Fio", "papel": "Coordenador", "vigencia_fim": "2026-12-31"}
        ]
    }, 
    {
        "nome": "Aline Bezerra Soares", "cpf": "777.777.777-77", "siape": "7788990", "unidade_lotacao": "FAODO", 
        "titulacao": "Doutor", "pq": False, 
        "pendencias": [], 
        "projetos_em_andamento": []
    }, 
    {
        "nome": "Roberto Yamashita", "cpf": "888.888.888-88", "siape": "8899001", "unidade_lotacao": "FAENG", 
        "titulacao": "Doutor", "pq": True, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.8055.2023", "titulo": "Projeto de Fonte de Alimentação Linear 12V e 5V", "papel": "Coordenador", "vigencia_fim": "2025-12-31"}
        ]
    },
    {
        "nome": "Juliana Prado", "cpf": "999.999.999-99", "siape": "9900112", "unidade_lotacao": "FAENG", 
        "titulacao": "Doutor", "pq": False, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.9066.2024", "titulo": "Multiplexação de Matriz de LEDs com Microcontrolador 8051", "papel": "Coordenador", "vigencia_fim": "2026-05-30"}
        ]
    },
    {   
         "nome": "Patrícia Helena Moura", "cpf": "404.404.404-40", "siape": "4044556", "unidade_lotacao": "FACOM",
        "titulacao": "Doutor", "pq": True,
        "pendencias": [],
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.4099.2025", "titulo": "Inteligência Artificial Explicável para Diagnóstico Médico", "papel": "Coordenador", "vigencia_fim": "2027-07-31"}
        ]
    },
    {
        "nome": "Eduardo Henrique Lima", "cpf": "505.505.505-50", "siape": "5055667", "unidade_lotacao": "FAENG",
        "titulacao": "Mestre", "pq": False,
        "pendencias": [],
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.5101.2024", "titulo": "Desenvolvimento de Robôs Móveis Autônomos", "papel": "Coordenador", "vigencia_fim": "2026-09-20"}
        ]
    },
    {
        "nome": "Larissa Nogueira Alves", "cpf": "606.606.606-60", "siape": "6066778", "unidade_lotacao": "INISA",
        "titulacao": "Doutor", "pq": False,
        "pendencias": [
            {"id_pendencia": "PEND-2025-021", "tipo": "Relatório Parcial", "descricao": "Relatório parcial não enviado", "data_vencimento": "2025-09-10", "impeditiva": False}
        ],
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.6122.2025", "titulo": "Análise Preditiva em Dados Epidemiológicos", "papel": "Coordenador", "vigencia_fim": "2027-03-15"}
        ]
    },
    {
        "nome": "Thiago Martins Ribeiro", "cpf": "707.707.707-70", "siape": "7077889", "unidade_lotacao": "FACOM",
        "titulacao": "Doutor", "pq": True,
        "pendencias": [],
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.7144.2024", "titulo": "Segurança Cibernética em Infraestruturas Críticas", "papel": "Coordenador", "vigencia_fim": "2026-12-10"}
        ]
    },
    {
        "nome": "Mariana Coutinho Freitas", "cpf": "808.808.808-80", "siape": "8088990", "unidade_lotacao": "FAMEZ",
        "titulacao": "Doutor", "pq": False,
        "pendencias": [],
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.8200.2025", "titulo": "Monitoramento Inteligente de Rebanhos com IoT", "papel": "Coordenador", "vigencia_fim": "2027-01-30"}
        ]
    },
    {
        "nome": "Ricardo Gomes", "cpf": "101.101.101-10", "siape": "1011223", "unidade_lotacao": "FAMEZ", 
        "titulacao": "Doutor", "pq": False, 
        "pendencias": [
            {"id_pendencia": "PEND-2025-010", "tipo": "Artigo não submetido", "descricao": "Falta de submissão de artigo do PIBIC anterior", "data_vencimento": "2025-12-01", "impeditiva": True}
        ], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.1077.2023", "titulo": "Automação de Estufa Agrícola com Controle de Temperatura e Iluminação", "papel": "Coordenador", "vigencia_fim": "2025-10-30"}
        ]
    },
    {
        "nome": "Camila Mendes", "cpf": "202.202.202-20", "siape": "2022334", "unidade_lotacao": "INISA", 
        "titulacao": "Doutor", "pq": True, 
        "pendencias": [], 
        "projetos_em_andamento": []
    },
    {
        "nome": "Fábio Lucena", "cpf": "303.303.303-30", "siape": "3033445", "unidade_lotacao": "FACOM", 
        "titulacao": "Mestre", "pq": False, 
        "pendencias": [], 
        "projetos_em_andamento": [
            {"id_sigproj": "SIG.3088.2024", "titulo": "Sistema de Repelente Automatizado usando Visão Computacional", "papel": "Coordenador", "vigencia_fim": "2026-11-15"}
        ]
    },
]

temas_projetos = [
    "Automação de Estufa Agrícola com Controle de Temperatura",
    "Sistema de Repelente Automatizado usando Visão Computacional",
    "Extração e Processamento de Dados do IBGE via Web Scraping",
    "Projeto de Fonte de Alimentação Linear 12V e 5V",
    "Multiplexação de Matriz de LEDs com Microcontrolador 8051",
    "Modelagem Relacional para Dados do Mercado Financeiro",
    "Configuração de Timers e Interrupções em Sistemas Embarcados",
    "Análise de Indicadores ESG na Administração Pública",
    "Implementação de Propriedades ACID em Bancos de Dados",
    "Desenvolvimento de Interface LCD para Sistemas de Controle",
     "Inteligência Artificial Explicável para Diagnóstico Médico",
    "Desenvolvimento de Robôs Móveis Autônomos",
    "Análise Preditiva em Dados Epidemiológicos",
    "Segurança Cibernética em Infraestruturas Críticas",
    "Monitoramento Inteligente de Rebanhos com IoT",
    "Aplicação de Redes Neurais em Reconhecimento Facial",
    "Sistema de Irrigação Automatizada com Sensores IoT",
    "Análise de Sentimentos em Redes Sociais",
    "Detecção de Fraudes Bancárias com Machine Learning",
    "Desenvolvimento de Chatbots para Atendimento Acadêmico",
    "Controle Inteligente de Consumo Energético Residencial",
    "Uso de Blockchain para Rastreamento Logístico",
    "Reconhecimento de Voz para Automação Residencial",
    "Predição de Séries Temporais Financeiras",
    "Sistema de Recomendação para Bibliotecas Digitais",
    "Simulação de Tráfego Urbano com Agentes Inteligentes",
    "Visão Computacional para Monitoramento Ambiental",
    "Análise de Dados Climáticos com Big Data",
    "Desenvolvimento de Aplicativos Inclusivos para Deficientes Visuais",
    "Modelagem de Sistemas Multiagentes",
    "Automação Industrial com CLPs e Supervisórios",
    "Detecção de Anomalias em Redes de Computadores",
    "Mineração de Dados em Ambientes Educacionais",
    "Otimização de Rotas para Veículos Autônomos",
    "Sistemas Embarcados para Agricultura de Precisão",
    "Aplicação de Deep Learning em Diagnóstico por Imagem",
    "Plataforma de Ensino Adaptativo com IA",
    "Análise de Vulnerabilidades em Aplicações Web",
    "Computação em Nuvem para Processamento Científico",
    "Internet das Coisas aplicada à Pecuária",
    "Sistema Inteligente de Gerenciamento Hospitalar",
    "Análise de Eficiência Energética em Edificações",
    "Reconhecimento de Padrões em Sinais Biomédicos",
    "Desenvolvimento de Jogos Educacionais Interativos",
    "Uso de Drones no Monitoramento Agrícola",
    "Arquitetura de Microsserviços para Sistemas Escaláveis",
    "Modelagem Matemática de Epidemias",
    "Análise Automatizada de Documentos Jurídicos",
    "Sistema de Monitoramento de Qualidade da Água",
    "Aplicações de Computação Quântica em Otimização"
]

def criar_lattes_xml(pesquisador, dir_path):
    import random
    cpf_limpo = pesquisador["cpf"].replace(".", "").replace("-", "")
    partes_nome = pesquisador["nome"].split()
    ultimo_nome = partes_nome[-1].upper()
    iniciais = " ".join([n[0] + "." for n in partes_nome[:-1]])
    nome_citacao = f"{ultimo_nome}, {iniciais}"

    root = Element("CURRICULO-VITAE", {
        "SISTEMA-ORIGEM-XML": "LATTES_OFFLINE",
        "NUMERO-IDENTIFICADOR": str(random.randint(1000000000000000, 9999999999999999)),
        "DATA-ATUALIZACAO": "12022026",
        "HORA-ATUALIZACAO": "152123"
    })
    
    dados_gerais = SubElement(root, "DADOS-GERAIS", {
        "NOME-COMPLETO": pesquisador["nome"],
        "NOME-EM-CITACOES-BIBLIOGRAFICAS": nome_citacao,
        "NACIONALIDADE": "B",
        "CPF": cpf_limpo,
        "NUMERO-DO-PASSAPORTE": "",
        "PAIS-DE-NASCIMENTO": "Brasil",
        "UF-NASCIMENTO": "MS",
        "CIDADE-NASCIMENTO": "Campo Grande",
        "DATA-NASCIMENTO": "01011980",
        "SEXO": random.choice(["MASCULINO", "FEMININO"]),
        "RACA-OU-COR": "Branca"
    })
    
    SubElement(dados_gerais, "RESUMO-CV", {
        "TEXTO-RESUMO-CV-RH": f"Pesquisador(a) com graduação, mestrado e doutorado. Atualmente atua como docente e pesquisador(a) em projetos de inovação tecnológica.",
        "TEXTO-RESUMO-CV-RH-EN": "Researcher with experience in Engineering and Computer Science."
    })
    
    endereco = SubElement(dados_gerais, "ENDERECO", {"FLAG-DE-PREFERENCIA": "ENDERECO_PROFISSIONAL"})
    SubElement(endereco, "ENDERECO-PROFISSIONAL", {
        "NOME-INSTITUICAO-EMPRESA": "Universidade Federal de Mato Grosso do Sul",
        "CIDADE": "Campo Grande",
        "UF": "MS",
        "CEP": "79070900",
        "PAIS": "Brasil",
        "E-MAIL": "pesquisador.teste@ufms.br"
    })
    
    formacao = SubElement(dados_gerais, "FORMACAO-ACADEMICA-TITULACAO")
    SubElement(formacao, "GRADUACAO", {
        "SEQUENCIA-FORMACAO": "1",
        "NOME-CURSO": "Engenharia de Computação",
        "STATUS-DO-CURSO": "CONCLUIDO",
        "ANO-DE-INICIO": "1998",
        "ANO-DE-CONCLUSAO": "2002",
        "NOME-INSTITUICAO": "Universidade Federal de Mato Grosso do Sul"
    })
    
    if pesquisador["titulacao"] in ["Mestre", "Doutor"]:
        SubElement(formacao, "MESTRADO", {
            "SEQUENCIA-FORMACAO": "2",
            "NOME-CURSO": "Mestrado em Ciências da Computação",
            "STATUS-DO-CURSO": "CONCLUIDO",
            "ANO-DE-INICIO": "2003",
            "ANO-DE-CONCLUSAO": "2005",
            "NOME-INSTITUICAO": "Universidade Federal de Mato Grosso do Sul"
        })
        
    if pesquisador["titulacao"] == "Doutor":
        SubElement(formacao, "DOUTORADO", {
            "SEQUENCIA-FORMACAO": "3",
            "NOME-CURSO": "Doutorado em Engenharia Elétrica",
            "STATUS-DO-CURSO": "CONCLUIDO",
            "ANO-DE-INICIO": "2006",
            "ANO-DE-CONCLUSAO": "2010",
            "NOME-INSTITUICAO": "Universidade de São Paulo"
        })

    atuacoes = SubElement(dados_gerais, "ATUACOES-PROFISSIONAIS")
    atuacao = SubElement(atuacoes, "ATUACAO-PROFISSIONAL", {
        "CODIGO-INSTITUICAO": "087000000006",
        "NOME-INSTITUICAO": "Universidade Federal de Mato Grosso do Sul",
        "SEQUENCIA-ATIVIDADE": "1"
    })
    
    SubElement(atuacao, "VINCULOS", {
        "TIPO-DE-VINCULO": "Servidor Publico",
        "ENQUADRAMENTO-FUNCIONAL": "Professor Adjunto",
        "CARGA-HORARIA-SEMANAL": "40",
        "FLAG-DEDICACAO-EXCLUSIVA": "SIM",
        "ANO-INICIO": "2011",
        "FLAG-VINCULO-EMPREGATICIO": "SIM"
    })
    
    if pesquisador["pq"]:
        SubElement(atuacao, "VINCULOS", {
            "TIPO-DE-VINCULO": "Bolsista de Produtividade",
            "ORGAO": "CNPq",
            "ENQUADRAMENTO-FUNCIONAL": "Pesquisador",
            "ANO-INICIO": "2020",
            "FLAG-VINCULO-EMPREGATICIO": "NAO"
        })
        
    SubElement(atuacao, "ATIVIDADES-DE-PESQUISA-E-DESENVOLVIMENTO")
    
    rough_string = tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    
    xml_str = reparsed.toprettyxml(indent="  ", encoding="ISO-8859-1").decode("ISO-8859-1")
    xml_str = xml_str.replace('<?xml version="1.0" encoding="ISO-8859-1"?>', '<?xml version="1.0" encoding="ISO-8859-1" standalone="no"?>')

    with open(os.path.join(dir_path, "lattes.xml"), "w", encoding="ISO-8859-1") as f:
        f.write(xml_str)


def criar_ficha_pontuacao(dir_path, tipo_erro="correto"):
    import random
    import pandas as pd
    import os

    elementos = [
        ("", "PARTE I – Produção científica, tecnológica e/ou artística a partir de janeiro de 2020 (inclusive)...", "", None, ""),
        ("1", "Produção científica, tecnológica e/ou artística", "", None, "Obs: A ficha de pontuação é protegia..."),
        ("", "1.1. Artigo publicado, indexado com conceito A1 (QUALIS) / Percentil na plataforma SCOPUS de 100% a 88%", "sem teto", 10.0, ""),
        ("", "1.2. Artigo publicado, indexado com conceito A2 (QUALIS) / Percentil na plataforma SCOPUS de 87% a 76%", "sem teto", 8.5, ""),
        ("", "1.3. Artigo publicado, indexado com conceito A3 (QUALIS) / Percentil na plataforma SCOPUS de 75% a 63%", "sem teto", 7.0, ""),
        ("", "1.4. Artigo publicado, indexado com conceito A4 (QUALIS) / Percentil na plataforma SCOPUS de 62% a 50%", "sem teto", 5.5, ""),
        ("", "1.5. Artigo publicado, indexado com conceito B1 (QUALIS) / Percentil na plataforma SCOPUS de 49% a 37%", "sem teto", 4.0, ""),
        ("", "1.6. Artigo publicado, indexado com conceito B2 (QUALIS) / Percentil na plataforma SCOPUS de 36% a 25%", "sem teto", 2.5, ""),
        ("", "1.7. Artigo publicado, indexado com conceito B3 (QUALIS) / Percentil na plataforma SCOPUS de 24% a 13%", "sem teto", 1.5, ""),
        ("", "1.8. Artigo publicado, indexado com conceito B4 (QUALIS) / Percentil na plataforma SCOPUS de 12% a 1%", "sem teto", 1.0, ""),
        ("", "1.9. Trabalhos de divulgação artística em periódicos", "sem teto", 2.0, ""),
        ("", "1.10. Resenhas bibliográficas internacionais", "sem teto", 2.0, ""),
        ("", "1.11. Resenhas bibliográficas nacionais", "sem teto", 1.0, ""),
        ("", "1.12. Prefácio, Posfácio e verbetes", "sem teto", 1.0, ""),
        
        ("", "Digite as informações dos periódicos com artigos publicados ou aceitos - PARTE I - Item 1.1 a 1.8 da Tabela (Plataforma Sucupira ou Plataforma Scopus):", "", "MARKER_PERIODICOS", ""),
        
        ("2", "Propriedade Intelectual", "", None, ""),
        ("", "2.1. Patente aceita", "sem teto", 10.0, ""),
        ("", "2.2. Patente depositada", "sem teto", 7.0, ""),
        ("3", "Livros e Capítulos", "", None, ""),
        ("", "3.1. Livros publicados (com ISBN)", "sem teto", 5.0, ""),
        ("", "3.2. Capítulos de livros publicados", "sem teto", 3.0, ""),
        ("", "3.3. Tradução de livros completos", "sem teto", 4.0, ""),
        ("", "3.4. Tradução de capítulos de livros", "sem teto", 2.0, ""),
        ("", "3.5. Organização e editoração de livros", "sem teto", 4.0, ""),
        ("", "3.6. Confecção de mapas, cartas geográficas e maquetes", "sem teto", 4.0, ""),
        ("", "3.7. Assessoria/Consultoria científica/Parecer ad hoc", "sem teto", 1.0, ""),
        ("Somatório 1", "", "", "SUM", ""),
        ("", "PARTE II – Experiência profissional a partir de janeiro de 2020...", "", None, ""),
        ("4", "Orientações Concluídas", "", None, ""),
        ("", "4.1. Trabalho de conclusão de curso de graduação", "5", 1.0, ""),
        ("", "4.2. Iniciação Científica (PIBIC/PIBITI etc)", "5", 2.0, ""),
        ("", "4.3. Tutoria PET", "1", 20.0, ""),
        ("", "4.4. Doutorado", "10", 10.0, ""),
        ("", "4.5. Mestrado", "10", 5.0, ""),
        ("", "4.6. Especialização", "10", 2.0, ""),
        ("", "4.7. Pós-Doutorado", "5", 3.0, ""),
        ("", "4.8. Coorientação de Doutorado", "5", 3.0, ""),
        ("", "4.9. Coorientação de Mestrado", "5", 1.5, ""),
        ("", "4.10. Tutor ou Preceptor de Residência", "5", 1.5, ""),
        ("5", "Bancas Examinadoras", "", None, ""),
        ("", "5.1. Qualificação de Doutorado", "10", 2.0, ""),
        ("", "5.2. Defesa de Tese de Doutorado", "10", 6.0, ""),
        ("", "5.3. Qualificação de Mestrado", "10", 1.0, ""),
        ("", "5.4. Defesa de Dissertação de Mestrado", "10", 3.0, ""),
        ("", "5.5. Avaliação de TFC (lato sensu)", "10", 1.0, ""),
        ("", "5.6. Concurso Público, avaliação de IES ou PIBIC", "10", 3.0, ""),
        ("", "5.7. Professor Titular", "10", 3.0, ""),
        ("6", "Atuação Institucional", "", None, ""),
        ("", "6.1. Professor Permanente (por programa)", "10", 5.0, ""),
        ("", "6.2. Professor Colaborador (por programa)", "10", 2.0, ""),
        ("", "6.3. Professor com bolsa de produtividade - CNPq", "1", 50.0, ""),
        ("", "6.4. Coordenador de projeto com fomento", "10", 10.0, ""),
        ("", "6.5. Líder de grupo de pesquisa", "1", 2.0, ""),
        ("Somatório 2", "", "", "SUM", ""),
        ("", "PARTE III – Produção artística e cultural e organização de eventos", "", None, ""),
        ("7", "Produção artística e cultural e organização de eventos", "", None, ""),
        ("", "7.1. Apresentação de Obra Artística", "sem teto", 4.0, ""),
        ("", "7.2. Criação de Obra Artística", "sem teto", 4.0, ""),
        ("", "7.3. Produção de Evento Cultural/Artístico", "10", 4.0, ""),
        ("", "7.4. Coordenador de evento internacional cadastrado na UFMS", "10", 4.0, ""),
        ("", "7.5. Coordenador de evento nacional cadastrado na UFMS", "10", 2.0, ""),
        ("", "7.6. Coordenador de evento local cadastrado na UFMS", "10", 1.0, ""),
        ("Somatório 3", "", "", "SUM", ""),
        ("TOTAL DA PONTUAÇÃO (Somatório 1 + 2 + 3)", "", "", "FINAL_SUM", "")
    ]

    colunas = ["Nº", "Critério", "Máx.(Qtde)", "Qtde", "Peso (valor)", "Total", "Obs"]
    dados = {c: [] for c in colunas}
    
    soma_atual = 0.0
    soma_geral = 0.0
    qtd_artigos_total = 0

    qtd_por_criterio = {}
    for num, crit, max_q, peso, obs in elementos:
        if isinstance(peso, float):
            if random.random() > 0.85: 
                qtd = random.randint(1, 2)
            else:
                qtd = 0
            qtd_por_criterio[crit] = qtd
            
            if crit.startswith(("1.1.", "1.2.", "1.3.", "1.4.", "1.5.", "1.6.", "1.7.", "1.8.")):
                qtd_artigos_total += qtd

    for num, crit, max_q, peso, obs in elementos:
        if peso == "MARKER_PERIODICOS":
            dados["Nº"].append("")
            dados["Critério"].append(crit)
            dados["Máx.(Qtde)"].append("")
            dados["Qtde"].append(None)
            dados["Peso (valor)"].append(None)
            dados["Total"].append(None)
            dados["Obs"].append("")
            
            dados["Nº"].append("")
            dados["Critério"].append("Título do Periódico")
            dados["Máx.(Qtde)"].append("ISSN (obrigatório somente para Plataforma Sucupira)")
            dados["Qtde"].append("Percentil (obrigatório somente para Plataforma Scopus) - consultar o item 6.7 do edital")
            dados["Peso (valor)"].append(None)
            dados["Total"].append(None)
            dados["Obs"].append("")

            qtd_periodicos = qtd_artigos_total
            if tipo_erro == "inconsistencia_artigos_periodicos":
                qtd_periodicos = qtd_artigos_total + random.choice([-1, 1])
                if qtd_periodicos < 0: qtd_periodicos = 1

            for p in range(max(2, qtd_periodicos)): 
                if p < qtd_periodicos:
                    titulo = f"Revista Científica Avançada {p+1}"
                    issn = f"{random.randint(1000,9999)}-{random.randint(1000,9999)}" if random.random() > 0.5 else None
                    perc = f"{random.randint(50, 99)}%" if not issn else None

                    if tipo_erro == "inconsistencia_artigos_periodicos" and random.random() > 0.6:
                        issn = None
                        perc = None

                    dados["Nº"].append("")
                    dados["Critério"].append(titulo)
                    dados["Máx.(Qtde)"].append(issn)
                    dados["Qtde"].append(perc)
                    dados["Peso (valor)"].append(None)
                    dados["Total"].append(None)
                    dados["Obs"].append("")
                else:
                    dados["Nº"].append("")
                    dados["Critério"].append("")
                    dados["Máx.(Qtde)"].append("")
                    dados["Qtde"].append(None)
                    dados["Peso (valor)"].append(None)
                    dados["Total"].append(None)
                    dados["Obs"].append("")
            continue

        dados["Nº"].append(num)
        dados["Critério"].append(crit)
        dados["Máx.(Qtde)"].append(max_q)
        dados["Obs"].append(obs)

        if peso is None:
            dados["Qtde"].append(None)
            dados["Peso (valor)"].append(None)
            dados["Total"].append(None)
            
        elif peso == "SUM":
            dados["Qtde"].append(None)
            dados["Peso (valor)"].append(None)
            dados["Total"].append(soma_atual)
            soma_geral += soma_atual
            soma_atual = 0.0
            
        elif peso == "FINAL_SUM":
            dados["Qtde"].append(None)
            dados["Peso (valor)"].append(None)
            dados["Total"].append(soma_geral)
            
        else:
            qtd = qtd_por_criterio[crit]
            sub = float(qtd * peso)
            soma_atual += sub

            dados["Qtde"].append(qtd)
            dados["Peso (valor)"].append(peso)
            dados["Total"].append(sub)

    if tipo_erro == "soma_errada":
        dados["Total"][-1] = soma_geral - random.choice([10.0, 15.0, 20.0])
        
    elif tipo_erro == "multiplicacao_errada":
        linhas_validas = [i for i, p in enumerate(dados["Peso (valor)"]) if isinstance(p, float) and dados["Qtde"][i] > 0]
        if not linhas_validas: 
            dados["Qtde"][2] = 2
            dados["Total"][2] = 20.0
            linhas_validas = [2]
            
        linha_alvo = random.choice(linhas_validas)
        dados["Total"][linha_alvo] += random.choice([5.0, -5.0])
        
        somas_partes = [0.0, 0.0, 0.0]
        parte = 0
        for i, p in enumerate(dados["Peso (valor)"]):
            if isinstance(p, float): somas_partes[parte] += dados["Total"][i]
            elif dados["Critério"][i] == "Somatório 1": dados["Total"][i] = somas_partes[0]; parte = 1
            elif dados["Critério"][i] == "Somatório 2": dados["Total"][i] = somas_partes[1]; parte = 2
            elif dados["Critério"][i] == "Somatório 3": dados["Total"][i] = somas_partes[2]
        dados["Total"][-1] = sum(somas_partes)
        
    elif tipo_erro == "campo_vazio":
        linhas_validas = [i for i, q in enumerate(dados["Qtde"]) if isinstance(q, int) and q > 0]
        if not linhas_validas: 
            linhas_validas = [i for i, p in enumerate(dados["Peso (valor)"]) if isinstance(p, float)]
            
        linha_alvo = random.choice(linhas_validas)
        dados["Qtde"][linha_alvo] = None 
        dados["Total"][linha_alvo] = None 
        dados["Total"][-1] = "" 
        
    elif tipo_erro == "coluna_nome_errado":
        mapa_renomear = {"Qtde": "Quantidade Declarada", "Peso (valor)": "Pontos", "Total": "Subtotal Parcial"}
        col_alvo = random.choice(list(mapa_renomear.keys()))
        dados = {mapa_renomear[col_alvo] if k == col_alvo else k: v for k, v in dados.items()}

    df = pd.DataFrame(dados)
    df.to_excel(os.path.join(dir_path, "ficha_pontuacao.xlsx"), index=False)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Base interna salva mantendo os objetos completos
    base_interna = []
    for p in pesquisadores:
        base_interna.append({
            "cpf": p["cpf"],
            "siape": p["siape"],
            "unidade_lotacao": p["unidade_lotacao"],
            "pendencias_propp": p["pendencias"],
            "projetos_em_andamento": p["projetos_em_andamento"]
        })
    with open(os.path.join(OUTPUT_DIR, "base_interna.json"), "w", encoding="utf-8") as f:
        json.dump(base_interna, f, indent=4)
        
    print(f"Base interna gerada com sucesso em '{OUTPUT_DIR}/base_interna.json'")

    pesquisadores_selecionados = []
    pesquisadores_selecionados.extend([pesquisadores[0]] * 4) 
    pesquisadores_selecionados.extend([pesquisadores[1]] * 3)
    
    while len(pesquisadores_selecionados) < NUM_PROPOSTAS:
        pesquisadores_selecionados.append(random.choice(pesquisadores[2:]))

    random.shuffle(pesquisadores_selecionados)

    tipos_ficha = ["correto", "campo_vazio", "soma_errada", "multiplicacao_errada", "coluna_nome_errado", "inconsistencia_artigos_periodicos"]
    pesos_ficha = [0.40, 0.10, 0.10, 0.10, 0.10, 0.20] 

    for i, pesquisador in enumerate(pesquisadores_selecionados):
        prop_id = f"PROPOSTA_{str(i+1).zfill(3)}"
        prop_dir = os.path.join(OUTPUT_DIR, prop_id)
        os.makedirs(prop_dir, exist_ok=True)
        
        tema_base = random.choice(temas_projetos)
        titulo_unico = f"{tema_base} - Estudo de Caso {i+1:03d}"

        sigla_modalidade = random.choice(["PIBIC", "PIBITI", "PIBIC-AF"])
        mapa_programas = {
            "PIBIC": "PIBIC - Programa Institucional de Bolsas de Iniciação Científica",
            "PIBITI": "PIBITI - Programa Institucional de Bolsas de Iniciação em Desenvolvimento Tecnológico e Inovação",
            "PIBIC-AF": "PIBIC-AF - Programa Institucional de Bolsas de Iniciação Científica Nas Ações Afirmativas"
        }
        
        # 2. Adaptação para ler o título do dicionário de projetos do pesquisador
        titulo_andamento = pesquisador["projetos_em_andamento"][0]["titulo"] if pesquisador["projetos_em_andamento"] else "Nenhum projeto informado"
        
        formulario = {
            "id_proposta": prop_id,
            "dados_coordenador": {
                "nome": pesquisador["nome"],
                "1_nivel_academico": "Doutorado" if pesquisador["titulacao"] == "Doutor" else "Mestrado",
                "2_vinculo_institucional": "Docente efetivo do quadro",
                "3_pos_graduacao": "Membro permanente do Programa de Pós-Graduação stricto sensu da UFMS.",
                "4_link_lattes": f"http://lattes.cnpq.br/{random.randint(1000000000000000, 9999999999999999)}",
                "5_numero_orcid": f"0000-000{random.randint(1,9)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
                "6_cpf": pesquisador["cpf"],
                "22_retorno_licenca_maternidade_ou_adotante": "Não",
                "23_servidor_empossado_ultimos_tres_anos": "Não"
            },
            "dados_projeto": {
                "7_titulo_plano_trabalho": titulo_unico,
                "8_palavras_chave": ["Simulação", "Tecnologia", "Inovação"],
                "9_programa": mapa_programas[sigla_modalidade],
                "10_areas_conhecimento": ["Engenharias"],
                "11_titulo_projeto_pesquisa_em_andamento": titulo_andamento,
                "12_nome_coordenador_projeto_andamento": pesquisador["nome"],
                "13_unidade_executora": pesquisador["unidade_lotacao"],
                "14_unidade_orgao_execucao": "Universidade Federal de Mato Grosso do Sul",
                "15_inicio_previsto": "01/09/2024",
                "16_duracao_meses": 12,
                "17_gera_patente": "Não",
                "18_possui_inovacao_tecnologica": "Sim",
                "19_objetivos_desenvolvimento_sustentavel": ["ODS 9: Construir infraestruturas resilientes, promover a industrialização inclusiva e sustentável e fomentar a inovação"],
                "20_areas_prioritarias_mcti": "Tecnologias Estratégicas",
                "21_areas_estrategicas_ms": "Bioeconomia e Agronegócio",
                "24_envolve_estudante_em_projeto_ciencia_basica": "Sim",
                "25_ficha_pontuacao_arquivo": "ficha_pontuacao.xlsx",
                "26_introducao_justificativa": "A justificativa deste projeto baseia-se na necessidade regional de automação...",
                "27_objetivos": "O objetivo principal é projetar, implementar e validar um sistema computacional...",
                "28_metodologia": "Será empregada uma metodologia ágil dividida em três fases principais de desenvolvimento...",
                "29_resultados_esperados": "Espera-se como resultado a publicação de pelo menos um artigo científico e o desenvolvimento de um protótipo.",
                "30_impacto_social": "Melhoria direta no setor produtivo local e formação de recursos humanos qualificados.",
                "31_cronograma": [
                    {"atividade": "Revisão Bibliográfica", "mes_inicio": 1, "duracao_meses": 2},
                    {"atividade": "Desenvolvimento do Protótipo", "mes_inicio": 3, "duracao_meses": 6},
                    {"atividade": "Escrita e Submissão de Artigo", "mes_inicio": 9, "duracao_meses": 3}
                ],
                "32_referencias": "SILVA, A. Computação Aplicada. 2. ed. São Paulo: Editora XPTO, 2023.",
                "33_anexo_plano_trabalho_pdf": "plano_trabalho_completo.pdf"
            },
            "dados_estudante": {
                "34_programa_contemplado_resultado_final": f"{sigla_modalidade}-UFMS (Programa de Iniciação com fomento da UFMS)",
                "35_nome_estudante": f"Estudante Bolsista {i+1}",
                "36_sexo": random.choice(["Feminino", "Masculino"]),
                "37_autodeclaracao_etnica": random.choice(["Branca", "Parda", "Preta", "Indígena", "Amarela", "Não declarada"]),
                "38_tipo_vaga": random.choice(["Ampla concorrência", "Cota"]),
                "39_passaporte_ufms": f"estudante.{i+1:03d}@ufms.br",
                "40_unidade": pesquisador["unidade_lotacao"],
                "41_cpf": f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
                "42_rga": f"202{random.randint(1000000,9999999)}",
                "43_curso": "Ciência da Computação",
                "44_link_curriculo_lattes": f"http://lattes.cnpq.br/{random.randint(1000000000000000, 9999999999999999)}",
                "45_email": f"estudante.{i+1:03d}@ufms.br",
                "46_telefone": "(67) 99999-0000",
                "47_informacoes_bancarias": {
                    "banco": "Banco do Brasil",
                    "codigo_banco": "001",
                    "numero_agencia": "1234",
                    "numero_conta": "5678-9"
                },
                "48_termo_concessao_ou_responsabilidade": "termo_assinado.pdf",
                "49_substituicao_estudante": "Não"
            }
        }
        
        with open(os.path.join(prop_dir, "formulario.json"), "w", encoding="utf-8") as f:
            json.dump(formulario, f, indent=4)
            
        criar_lattes_xml(pesquisador, prop_dir)
        
        tipo_escolhido = random.choices(tipos_ficha, weights=pesos_ficha, k=1)[0]
        criar_ficha_pontuacao(prop_dir, tipo_erro=tipo_escolhido)

    print(f"{NUM_PROPOSTAS} propostas sintéticas geradas com sucesso no diretório '{OUTPUT_DIR}/'.")

if __name__ == "__main__":
    main()