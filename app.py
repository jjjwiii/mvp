from flask import Flask, request, jsonify, render_template
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import sqlite3
import uuid




# Cria a instância do Flask
app = Flask(__name__)
app.secret_key = 'Josue@123'  # Defina uma chave secreta para a sessão

# Configurações para upload de arquivos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Garante que a pasta de uploads exista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def db_connect():
    conn = sqlite3.connect("multinivel.db", check_same_thread=False)
    cursor = conn.cursor()

    # Criar tabela de usuários
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT,
                        email TEXT UNIQUE,
                        whatsapp TEXT,
                        senha TEXT,  -- Nova coluna para armazenar a senha
                        codigo_indicacao TEXT UNIQUE,
                        indicado_por TEXT,
                        comprou INTEGER DEFAULT 0)''')
    
    # Criar tabela de indicações (afiliação)
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        indicado_id INTEGER,
                        nivel INTEGER)''')
    
    # Criar tabela de vendas
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        valor REAL,
                        data_compra TEXT)''')
    
    # Criar tabela de comissões
    cursor.execute('''CREATE TABLE IF NOT EXISTS commissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        afiliado_id INTEGER,
                        valor_comissao REAL,
                        nivel INTEGER,  -- Nível da comissão (1 a 9)
                        pago INTEGER DEFAULT 0,
                        data_compra TEXT,
                        FOREIGN KEY (afiliado_id) REFERENCES users(id))''')
    

    # Criar tabela de saques
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdrawals (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        nome_afiliado TEXT,  -- Adicionando o nome do afiliado
        chave_pix TEXT,
        valor REAL,
        status INTEGER DEFAULT 0,  -- 0 = Pendente, 1 = Pago
        data_solicitacao TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')


 # Criar tabela de produtos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        descricao TEXT,
        preco REAL,
        link_afiliado TEXT,
        foto TEXT,  -- Nova coluna para armazenar o caminho da foto
        user_id INTEGER,
        data_cadastro TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Criar tabela de usuários com login
    cursor.execute('''CREATE TABLE IF NOT EXISTS users_login (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT,
                        email TEXT UNIQUE,
                        senha TEXT)''')
    

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS webhook_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plataforma TEXT UNIQUE,  -- Nome da plataforma (Kirvano, Logzz, etc.)
        token TEXT UNIQUE,       -- Token único para a plataforma
        data_criacao TEXT        -- Data de criação do token
    )
''')
    

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuario_webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,               -- ID do usuário (afiliado/produtor)
        plataforma TEXT,               -- Nome da plataforma (Kirvano, Logzz, etc.)
        token TEXT UNIQUE,             -- Token único para o webhook
        data_criacao TEXT,             -- Data de criação do webhook
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS webhook_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,               -- ID do usuário (afiliado/produtor)
        token TEXT,                    -- Token do webhook
        dados TEXT,                    -- Dados recebidos (em formato JSON)
        data_recebimento TEXT,         -- Data de recebimento do webhook
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendas_mensais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,               -- ID do usuário (afiliado)
        mes_ano TEXT,                  -- Mês e ano no formato YYYY-MM
        valor_vendido REAL,            -- Valor total vendido no mês
        ativo INTEGER DEFAULT 0,       -- 0 = Inativo, 1 = Ativo
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

    
    conn.commit()
    return conn

db_connect()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/cadastro", methods=["POST"])
def cadastro():
    data = request.json
    nome = data["nome"]
    email = data["email"]
    whatsapp = data["whatsapp"]
    ref = data.get("ref")  # Código do afiliado
    codigo_indicacao = str(uuid.uuid4())[:8]  # Código único
    
    conn = db_connect()
    cursor = conn.cursor()

    # Verifica se o e-mail já está cadastrado
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        return jsonify({"error": "E-mail já cadastrado. Tente outro e-mail."}), 400
    
    # Insere o novo usuário se o e-mail não existir
    cursor.execute("INSERT INTO users (nome, email, whatsapp, codigo_indicacao, indicado_por) VALUES (?, ?, ?, ?, ?)", 
                   (nome, email, whatsapp, codigo_indicacao, ref))
    user_id = cursor.lastrowid

    if ref:
        cursor.execute("SELECT id FROM users WHERE codigo_indicacao = ?", (ref,))
        ref_user = cursor.fetchone()
        if ref_user:
            cursor.execute("INSERT INTO referrals (user_id, indicado_id, nivel) VALUES (?, ?, ?)", 
                           (ref_user[0], user_id, 1))

    conn.commit()
    conn.close()

    # Redireciona para a página do link de convite
    return jsonify({"message": "Cadastro realizado!", "link_indicacao": f"/convite/{codigo_indicacao}"})


@app.route("/cadastro_usuario", methods=["GET", "POST"])
def cadastro_usuario():
    if request.method == "GET":
        return render_template("cadastro_usuario.html")
    
    # Processar o formulário de cadastro
    data = request.json
    nome = data.get("nome")
    email = data.get("email")
    whatsapp = data.get("whatsapp")
    senha = data.get("senha")
    ref = data.get("ref")  # Código do afiliado (opcional)

    if not nome or not email or not whatsapp or not senha:
        return jsonify({"success": False, "error": "Todos os campos são obrigatórios."}), 400

    conn = db_connect()
    cursor = conn.cursor()

    # Verifica se o e-mail já está cadastrado
    cursor.execute("SELECT id, senha FROM users WHERE email = ?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        user_id, existing_password = existing_user
        if existing_password:  # Se já existe uma senha cadastrada
            conn.close()
            return jsonify({"success": False, "error": "E-mail já cadastrado com senha definida."}), 400
        else:  # Se não existe senha cadastrada, atualiza a senha
            senha_hash = generate_password_hash(senha)
            cursor.execute("UPDATE users SET senha = ? WHERE id = ?", (senha_hash, user_id))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "Senha atualizada com sucesso!"})
    else:
        # Gera um código de indicação único
        codigo_indicacao = str(uuid.uuid4())[:8]

        # Cria um hash da senha para armazenar no banco de dados
        senha_hash = generate_password_hash(senha)

        # Insere o novo usuário
        cursor.execute("INSERT INTO users (nome, email, whatsapp, senha, codigo_indicacao, indicado_por) VALUES (?, ?, ?, ?, ?, ?)", 
                       (nome, email, whatsapp, senha_hash, codigo_indicacao, ref))
        user_id = cursor.lastrowid

        if ref:
            cursor.execute("SELECT id FROM users WHERE codigo_indicacao = ?", (ref,))
            ref_user = cursor.fetchone()
            if ref_user:
                cursor.execute("INSERT INTO referrals (user_id, indicado_id, nivel) VALUES (?, ?, ?)", 
                               (ref_user[0], user_id, 1))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Cadastro realizado!", "link_indicacao": f"/convite/{codigo_indicacao}"})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    
    data = request.json
    email = data.get("email")
    senha = data.get("senha")

    if not email or not senha:
        return jsonify({"success": False, "error": "E-mail e senha são obrigatórios."}), 400

    conn = db_connect()
    cursor = conn.cursor()

    # Busca o usuário pelo e-mail
    cursor.execute("SELECT id, nome, senha, codigo_indicacao FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    conn.close()

    if user and check_password_hash(user[2], senha):  # Verifica a senha
        session['user_id'] = user[0]  # Armazena o user_id na sessão
        session['user_name'] = user[1]  # Armazena o nome do usuário na sessão
        session['codigo_indicacao'] = user[3]  # Armazena o código de indicação na sessão
        return jsonify({
            "success": True,
            "message": "Login realizado com sucesso!",
            "redirect": f"/painel/{user[3]}"  # Redireciona para o painel com o código de indicação
        })
    else:
        return jsonify({"success": False, "error": "E-mail ou senha incorretos."}), 401
    

    



@app.route("/comprar", methods=["POST"])
def comprar():
    if 'user_id' not in session:
        return jsonify({"error": "Usuário não autenticado."}), 401

    data = request.json
    user_id = session.get('user_id')
    valor = float(data.get("valor"))

    if not valor or valor <= 0:
        return jsonify({"error": "Valor da venda inválido."}), 400

    conn = db_connect()
    cursor = conn.cursor()

    try:
        # Registra a venda no banco de dados
        cursor.execute('''
            INSERT INTO sales (user_id, valor, data_compra)
            VALUES (?, ?, datetime('now'))
        ''', (user_id, valor))
        venda_id = cursor.lastrowid

        # Atualiza o valor vendido no mês
        mes_ano_atual = datetime.now().strftime("%Y-%m")
        cursor.execute('''
            UPDATE vendas_mensais 
            SET valor_vendido = valor_vendido + ? 
            WHERE user_id = ? AND mes_ano = ?
        ''', (valor, user_id, mes_ano_atual))

        # Verifica se o afiliado atingiu a meta de R$ 200 no mês
        cursor.execute('''
            SELECT valor_vendido 
            FROM vendas_mensais 
            WHERE user_id = ? AND mes_ano = ?
        ''', (user_id, mes_ano_atual))
        resultado = cursor.fetchone()

        if resultado and resultado[0] >= 200:
            cursor.execute('''
                UPDATE vendas_mensais 
                SET ativo = 1 
                WHERE user_id = ? AND mes_ano = ?
            ''', (user_id, mes_ano_atual))

        # Distribui as comissões para os níveis superiores
        nivel = 1
        afiliado_atual = user_id
        while nivel <= 9:
            # Busca o afiliado que indicou o afiliado atual
            cursor.execute('''
                SELECT indicado_por 
                FROM users 
                WHERE id = ?
            ''', (afiliado_atual,))
            resultado = cursor.fetchone()

            if not resultado or not resultado[0]:
                break  # Não há mais afiliados superiores

            afiliado_superior = resultado[0]

            # Define o percentual de comissão para o nível atual
            percentual_comissao = {
                1: 0.4,  # 40% no nível 1
                2: 0.02, # 2% nos níveis 2 a 9
                3: 0.02,
                4: 0.02,
                5: 0.02,
                6: 0.02,
                7: 0.02,
                8: 0.02,
                9: 0.02
            }.get(nivel, 0)

            # Calcula o valor da comissão
            valor_comissao = valor * percentual_comissao

            # Registra a comissão no banco de dados
            cursor.execute('''
                INSERT INTO commissions (afiliado_id, valor_comissao, nivel, pago, data_compra)
                VALUES (?, ?, ?, 0, datetime('now'))
            ''', (afiliado_superior, valor_comissao, nivel))

            # Avança para o próximo nível
            afiliado_atual = afiliado_superior
            nivel += 1

        conn.commit()
        return jsonify({"success": True, "message": "Venda registrada com sucesso!", "venda_id": venda_id})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()


@app.route("/painel/auth", methods=["POST"])
def painel_auth():
    email = request.form.get("email")

    conn = db_connect()
    cursor = conn.cursor()
    
    cursor.execute("SELECT codigo_indicacao FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    conn.close()

    if user:
        return redirect(url_for("painel", codigo=user[0]))  # Redireciona para /painel/<codigo>
    else:
        return "E-mail não encontrado. Tente novamente.", 404




@app.route("/painel", methods=["GET"])
def painel():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    user_id = session['user_id']
    conn = db_connect()
    cursor = conn.cursor()

    # Busca os dados do afiliado
    cursor.execute("SELECT id, nome, email, whatsapp, comprou, codigo_indicacao FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    codigo_indicacao = user[5]  # Código de indicação do usuário logado

    # Busca os indicados do afiliado
    cursor.execute("SELECT u.nome, u.email, u.whatsapp, u.comprou FROM users u JOIN referrals r ON u.id = r.indicado_id WHERE r.user_id = ?", (user_id,))
    indicacoes = cursor.fetchall()

    # Calcular o número de downlines (indicados)
    total_downlines = len(indicacoes)

    # Calcular o total de comissão ganha pelo afiliado
    cursor.execute('''SELECT c.valor_comissao 
                      FROM commissions c 
                      WHERE c.afiliado_id = ?''', (user_id,))
    comissoes = cursor.fetchall()

    # Somar as comissões (caso existam)
    total_comissao_afiliado = sum(comissao[0] for comissao in comissoes) if comissoes else 0

    # Calcular o número de downlines que realizaram compras
    cursor.execute('''SELECT COUNT(DISTINCT r.indicado_id) 
                      FROM referrals r 
                      JOIN users u ON r.indicado_id = u.id 
                      WHERE r.user_id = ? AND u.comprou = 1''', (user_id,))
    total_compras = cursor.fetchone()[0] or 0

    # Calcular o total de comissão baseado nas compras das downlines (74,90 cada compra)
    valor_da_comissao = 74.90
    total_comissao_compras = total_compras * valor_da_comissao

    # Total de comissão final: soma da comissão do afiliado com as comissões das compras dos downlines
    total_comissao_final = total_comissao_afiliado + total_comissao_compras

    conn.close()

    # Retorna os dados para o painel do afiliado
    return render_template("painel.html", nome=user[1], email=user[2], whatsapp=user[3], 
                           comprou=user[4], indicacoes=indicacoes, total_downlines=total_downlines, 
                           total_comissao=total_comissao_final, total_compras=total_compras)




@app.route("/convite/<codigo>", methods=["GET"])
def convite(codigo):
    return render_template("convite.html", codigo=codigo)


@app.route("/saque", methods=["GET"])
def saque():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    user_id = session.get('user_id')
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("SELECT valor, status FROM withdrawals WHERE user_id = ?", (user_id,))
    saques = cursor.fetchall()

    conn.close()

    return render_template("saque.html", saques=saques)


@app.route("/relatorios", methods=["GET"])
def relatorios():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = db_connect()
    cursor = conn.cursor()

    # Vendas pessoais no mês
    mes_ano_atual = datetime.now().strftime("%Y-%m")
    cursor.execute('''
        SELECT SUM(valor) 
        FROM sales 
        WHERE user_id = ? AND strftime('%Y-%m', data_compra) = ?
    ''', (user_id, mes_ano_atual))
    vendas_pessoais_mes = cursor.fetchone()[0] or 0

    # Comissões recebidas no mês
    cursor.execute('''
        SELECT SUM(valor_comissao) 
        FROM commissions 
        WHERE afiliado_id = ? AND strftime('%Y-%m', data_compra) = ?
    ''', (user_id, mes_ano_atual))
    comissoes_mes = cursor.fetchone()[0] or 0

    # Total de afiliados na rede
    cursor.execute('''
        SELECT COUNT(indicado_id) 
        FROM referrals 
        WHERE user_id = ?
    ''', (user_id,))
    total_afiliados_rede = cursor.fetchone()[0] or 0

    conn.close()

    return render_template("relatorios.html", vendas_pessoais_mes=vendas_pessoais_mes, 
                           comissoes_mes=comissoes_mes, total_afiliados_rede=total_afiliados_rede)


@app.route("/cadastrar_produtos", methods=["GET"])
def cadastrar_produtos():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    return render_template("cadastrar_produtos.html")


@app.route("/cadastrar_produto1", methods=["POST"])
def cadastrar_produto():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Usuário não autenticado."}), 401

    if 'foto' not in request.files:
        return jsonify({"success": False, "error": "Nenhuma foto enviada."}), 400

    foto = request.files['foto']
    if foto.filename == '':
        return jsonify({"success": False, "error": "Nenhuma foto selecionada."}), 400

    if foto and allowed_file(foto.filename):
        filename = secure_filename(foto.filename)
        foto_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        foto.save(foto_path)

        # Salva apenas o caminho relativo (sem 'static/')
        foto_relativa = os.path.join('uploads', filename)

        nome = request.form.get("nome")
        descricao = request.form.get("descricao")
        preco = request.form.get("preco")
        link_afiliado = request.form.get("link_afiliado")
        user_id = session.get("user_id")

        if not nome or not descricao or not preco or not link_afiliado or not user_id:
            return jsonify({"success": False, "error": "Todos os campos são obrigatórios."}), 400

        conn = db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO products (nome, descricao, preco, link_afiliado, foto, user_id, data_cadastro)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (nome, descricao, preco, link_afiliado, foto_relativa, user_id))

            conn.commit()
            return jsonify({"success": True, "message": "Produto cadastrado com sucesso!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()
    else:
        return jsonify({"success": False, "error": "Formato de arquivo não permitido."}), 400


@app.route("/meus_produtos", methods=["GET"])
def meus_produtos():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    return render_template("meus_produtos.html")


@app.route("/meus_produtos_json", methods=["GET"])
def meus_produtos_json():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Usuário não autenticado."}), 401

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, nome, descricao, preco, link_afiliado, foto, data_cadastro
        FROM products
        WHERE user_id = ?
    ''', (user_id,))

    produtos = cursor.fetchall()
    conn.close()

    return jsonify([{
        "id": produto[0],  # Adiciona o ID do produto
        "nome": produto[1],
        "descricao": produto[2],
        "preco": produto[3],
        "link_afiliado": produto[4],
        "foto": produto[5],
        "data_cadastro": produto[6]
    } for produto in produtos])


@app.route("/minhas_compras", methods=["GET"])
def minhas_compras():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    return render_template("minhas_compras.html")


@app.route("/vender", methods=["POST"])

def verificar_ativacao_mensal(user_id):
    conn = db_connect()
    cursor = conn.cursor()

    # Obtém o mês e ano atual
    mes_ano_atual = datetime.now().strftime("%Y-%m")

    # Verifica se o afiliado já tem um registro para o mês atual
    cursor.execute('''
        SELECT valor_vendido, ativo 
        FROM vendas_mensais 
        WHERE user_id = ? AND mes_ano = ?
    ''', (user_id, mes_ano_atual))
    registro = cursor.fetchone()

    if registro:
        valor_vendido, ativo = registro
        if valor_vendido >= 200 and ativo == 0:
            # Atualiza o status para ativo
            cursor.execute('''
                UPDATE vendas_mensais 
                SET ativo = 1 
                WHERE user_id = ? AND mes_ano = ?
            ''', (user_id, mes_ano_atual))
            conn.commit()
    else:
        # Insere um novo registro para o mês atual
        cursor.execute('''
            INSERT INTO vendas_mensais (user_id, mes_ano, valor_vendido, ativo)
            VALUES (?, ?, 0, 0)
        ''', (user_id, mes_ano_atual))
        conn.commit()

    conn.close()
def vender():
    if 'user_id' not in session:
        return jsonify({"error": "Usuário não autenticado."}), 401

    data = request.json
    user_id = session.get('user_id')
    valor = float(data.get("valor"))

    if not valor or valor <= 0:
        return jsonify({"error": "Valor da venda inválido."}), 400

    conn = db_connect()
    cursor = conn.cursor()

    try:
        # Registra a venda no banco de dados
        cursor.execute('''
            INSERT INTO sales (user_id, valor, data_compra)
            VALUES (?, ?, datetime('now'))
        ''', (user_id, valor))
        venda_id = cursor.lastrowid

        # Atualiza o valor vendido no mês
        mes_ano_atual = datetime.now().strftime("%Y-%m")
        cursor.execute('''
            UPDATE vendas_mensais 
            SET valor_vendido = valor_vendido + ? 
            WHERE user_id = ? AND mes_ano = ?
        ''', (valor, user_id, mes_ano_atual))

        # Verifica se o afiliado atingiu a meta de R$ 200 no mês
        cursor.execute('''
            SELECT valor_vendido 
            FROM vendas_mensais 
            WHERE user_id = ? AND mes_ano = ?
        ''', (user_id, mes_ano_atual))
        resultado = cursor.fetchone()

        if resultado and resultado[0] >= 200:
            cursor.execute('''
                UPDATE vendas_mensais 
                SET ativo = 1 
                WHERE user_id = ? AND mes_ano = ?
            ''', (user_id, mes_ano_atual))

        # Distribui as comissões para os níveis superiores
        nivel = 1
        afiliado_atual = user_id
        while nivel <= 9:
            # Busca o afiliado que indicou o afiliado atual
            cursor.execute('''
                SELECT indicado_por 
                FROM users 
                WHERE id = ?
            ''', (afiliado_atual,))
            resultado = cursor.fetchone()

            if not resultado or not resultado[0]:
                break  # Não há mais afiliados superiores

            afiliado_superior = resultado[0]

            # Define o percentual de comissão para o nível atual
            percentual_comissao = {
                1: 0.4,  # 40% no nível 1
                2: 0.02, # 2% nos níveis 2 a 9
                3: 0.02,
                4: 0.02,
                5: 0.02,
                6: 0.02,
                7: 0.02,
                8: 0.02,
                9: 0.02
            }.get(nivel, 0)

            # Calcula o valor da comissão
            valor_comissao = valor * percentual_comissao

            # Registra a comissão no banco de dados
            cursor.execute('''
                INSERT INTO commissions (afiliado_id, valor_comissao, nivel, pago, data_compra)
                VALUES (?, ?, ?, 0, datetime('now'))
            ''', (afiliado_superior, valor_comissao, nivel))

            # Avança para o próximo nível
            afiliado_atual = afiliado_superior
            nivel += 1

        conn.commit()
        return jsonify({"success": True, "message": "Venda registrada com sucesso!", "venda_id": venda_id})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()
       


@app.route("/minhas_afiliacoes", methods=["GET"])
def minhas_afiliacoes():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    return render_template("minhas_afiliacoes.html")


@app.route("/minhas_coproducoes", methods=["GET"])
def minhas_coproducoes():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    return render_template("minhas_coproducoes.html")


@app.route("/webhooks", methods=["GET"])
def webhooks():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    return render_template("webhooks.html")





@app.route("/editar_produto/<int:produto_id>", methods=["GET", "POST"])
def editar_produto(produto_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redireciona para o login se o usuário não estiver logado

    if request.method == "GET":
        # Busca os dados do produto no banco de dados
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, descricao, preco, link_afiliado, foto FROM products WHERE id = ? AND user_id = ?", (produto_id, session['user_id']))
        produto = cursor.fetchone()
        conn.close()

        if not produto:
            return jsonify({"success": False, "error": "Produto não encontrado ou você não tem permissão para editá-lo."}), 404

        return render_template("editar_produto.html", produto={
            "id": produto[0],
            "nome": produto[1],
            "descricao": produto[2],
            "preco": produto[3],
            "link_afiliado": produto[4],
            "foto": produto[5]
        })

    elif request.method == "POST":
        # Processa a edição do produto
        nome = request.form.get("nome")
        descricao = request.form.get("descricao")
        preco = request.form.get("preco")
        link_afiliado = request.form.get("link_afiliado")
        user_id = session.get("user_id")
        foto = request.files.get("foto")  # Obtém o arquivo de imagem

        if not nome or not descricao or not preco or not link_afiliado or not user_id:
            return jsonify({"success": False, "error": "Todos os campos são obrigatórios."}), 400

        conn = db_connect()
        cursor = conn.cursor()

        try:
            # Se uma nova foto foi enviada, processa o upload
            if foto and allowed_file(foto.filename):
                filename = secure_filename(foto.filename)
                foto_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                foto.save(foto_path)
                foto_relativa = os.path.join('uploads', filename)
            else:
                # Mantém a foto atual se nenhuma nova foto foi enviada
                cursor.execute("SELECT foto FROM products WHERE id = ?", (produto_id,))
                foto_relativa = cursor.fetchone()[0]

            # Atualiza os dados do produto
            cursor.execute('''
                UPDATE products
                SET nome = ?, descricao = ?, preco = ?, link_afiliado = ?, foto = ?
                WHERE id = ? AND user_id = ?
            ''', (nome, descricao, preco, link_afiliado, foto_relativa, produto_id, user_id))

            conn.commit()
            return jsonify({"success": True, "message": "Produto atualizado com sucesso!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()



@app.route("/admin")
def admin_panel():
    conn = db_connect()
    cursor = conn.cursor()

    # Obter todas as pessoas cadastradas e quem as indicou
    cursor.execute('''SELECT u.id, u.nome, u.email, u.whatsapp, u.comprou, r.user_id 
                      FROM users u 
                      LEFT JOIN referrals r ON u.id = r.indicado_id''')
    inscritos = cursor.fetchall()

    # Criar ranking de quem indicou mais pessoas
    cursor.execute('''SELECT u.id, u.nome, COUNT(r.indicado_id) AS total_indicados 
                      FROM users u 
                      LEFT JOIN referrals r ON u.id = r.user_id 
                      GROUP BY u.id 
                      ORDER BY total_indicados DESC''')
    ranking = cursor.fetchall()


    cursor.execute('''
    SELECT COUNT(r.indicado_id) AS total_indicados
    FROM referrals r
    ''')
    total_indicados = cursor.fetchone()[0]  # Extrair o valor da tupla



    # Obter todas as comissões por afiliado e nível
    cursor.execute('''SELECT c.afiliado_id, u.nome, c.nivel, SUM(c.valor_comissao) AS total_comissao
                      FROM commissions c 
                      JOIN users u ON c.afiliado_id = u.id
                      GROUP BY c.afiliado_id, c.nivel
                      ORDER BY c.nivel ASC, total_comissao DESC''')
    comissoes = cursor.fetchall()

    # Obter o total de inscritos
    cursor.execute("SELECT COUNT(id) FROM users")
    total_inscritos = cursor.fetchone()[0]

    # Obter o total de compradores
    cursor.execute("SELECT COUNT(id) FROM users WHERE comprou = 1")
    total_compradores = cursor.fetchone()[0]

    # Obter o total de inscritos por links de outras pessoas
    cursor.execute("SELECT COUNT(id) FROM users WHERE indicado_por IS NOT NULL")
    total_inscritos_links = cursor.fetchone()[0]

    # Calcular o total de comissões a serem pagas
    cursor.execute("SELECT SUM(valor_comissao) FROM commissions WHERE pago = 0")
    total_comissoes = cursor.fetchone()[0] or 0

    # Obter todas as solicitações de saque pendentes
    cursor.execute('''SELECT w.id, u.nome, w.chave_pix, w.valor, w.status 
                      FROM withdrawals w 
                      JOIN users u ON w.user_id = u.id 
                      WHERE w.status = 0''')  # Apenas saques pendentes
    saques_pendentes = cursor.fetchall()

    conn.close()

    # Passar as métricas para o template
    return render_template("admin.html", saques_pendentes=saques_pendentes, inscritos=inscritos, ranking=ranking, 
                           comissoes=comissoes, total_inscritos=total_inscritos, total_compradores=total_compradores, 
                           total_inscritos_links=total_inscritos_links, total_comissoes=total_comissoes, total_indicados=total_indicados)



@app.route("/webhooks", methods=["GET", "POST"])
def gerenciar_webhooks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = db_connect()
    cursor = conn.cursor()

    if request.method == "POST":
        plataforma = request.form.get("plataforma")

        if not plataforma:
            return jsonify({"success": False, "error": "Nome da plataforma é obrigatório."}), 400

        # Gera um token único
        token = str(uuid.uuid4())

        # Insere o novo webhook no banco
        cursor.execute('''
            INSERT INTO usuario_webhooks (user_id, plataforma, token, data_criacao)
            VALUES (?, ?, ?, datetime('now'))
        ''', (user_id, plataforma, token))
        conn.commit()

    # Lista todos os webhooks do usuário
    cursor.execute('''
        SELECT id, plataforma, token, data_criacao 
        FROM usuario_webhooks 
        WHERE user_id = ?
    ''', (user_id,))
    webhooks = cursor.fetchall()

    # Gera a URL do webhook com o token
    webhooks_com_url = []
    for webhook in webhooks:
        webhook_id, plataforma, token, data_criacao = webhook
        url_webhook = f"{request.host_url}webhook/{token}"  # URL com o token
        webhooks_com_url.append({
            "id": webhook_id,
            "plataforma": plataforma,
            "token": token,
            "url_webhook": url_webhook,
            "data_criacao": data_criacao
        })

    conn.close()

    return render_template("webhooks.html", webhooks=webhooks_com_url)

@app.route("/webhook/usuario", methods=["POST"])
def webhook_usuario():
    # Obtém o token do cabeçalho da requisição
    token = request.headers.get("Authorization")

    if not token:
        return jsonify({"error": "Token não fornecido"}), 401

    conn = db_connect()
    cursor = conn.cursor()

    # Verifica se o token é válido para o usuário
    cursor.execute('''
        SELECT user_id 
        FROM usuario_webhooks 
        WHERE token = ?
    ''', (token,))
    token_valido = cursor.fetchone()

    if not token_valido:
        conn.close()
        return jsonify({"error": "Token inválido"}), 403

    user_id = token_valido[0]

    # Processa os dados do webhook
    data = request.get_json()
    if not data or "email_comprador" not in data or "valor" not in data:
        return jsonify({"error": "Dados inválidos"}), 400

    email_comprador = data["email_comprador"]
    valor = float(data["valor"])

    # Busca o ID do usuário (produtor) dono do webhook
    cursor.execute('''
        SELECT id 
        FROM users 
        WHERE id = ?
    ''', (user_id,))
    produtor = cursor.fetchone()

    if not produtor:
        return jsonify({"error": "Usuário não encontrado"}), 404

    # Marca a compra como realizada
    cursor.execute("INSERT INTO sales (user_id, valor, data_compra) VALUES (?, ?, datetime('now'))", (user_id, valor))

    # Calcula e distribui a comissão (se necessário)
    # (Adicione a lógica de comissões aqui, se aplicável)

    conn.commit()
    conn.close()

    return jsonify({"success": "Webhook processado com sucesso!"}), 200


@app.route("/webhook/<token>", methods=["POST"])
def webhook(token):
    conn = db_connect()
    cursor = conn.cursor()

    # Verifica se o token é válido
    cursor.execute('''
        SELECT user_id 
        FROM usuario_webhooks 
        WHERE token = ?
    ''', (token,))
    token_valido = cursor.fetchone()

    if not token_valido:
        conn.close()
        return jsonify({"error": "Token inválido"}), 403

    user_id = token_valido[0]

    # Processa os dados do webhook
    data = request.get_json()
    if not data or "email_comprador" not in data or "valor" not in data:
        return jsonify({"error": "Dados inválidos"}), 400

    email_comprador = data["email_comprador"]
    valor = float(data["valor"])

    # Marca a compra como realizada
    cursor.execute("INSERT INTO sales (user_id, valor, data_compra) VALUES (?, ?, datetime('now'))", (user_id, valor))

    # Registra os dados recebidos no log
    dados_json = json.dumps(data)  # Converte os dados para JSON
    cursor.execute('''
        INSERT INTO webhook_logs (user_id, token, dados, data_recebimento)
        VALUES (?, ?, ?, datetime('now'))
    ''', (user_id, token, dados_json))

    # Calcula e distribui a comissão (se necessário)
    # (Adicione a lógica de comissões aqui, se aplicável)

    conn.commit()
    conn.close()

    return jsonify({"success": "Webhook processado com sucesso!"}), 200


@app.route("/webhook/kirvano", methods=["POST"])
def webhook_kirvano():
    data = request.get_json()

    if not data or "email_comprador" not in data or "valor" not in data:
        return jsonify({"error": "Dados inválidos"}), 400

    email_comprador = data["email_comprador"]
    valor = float(data["valor"])

    conn = db_connect()
    cursor = conn.cursor()

    # Verifica se o comprador está no banco e quem o indicou
    cursor.execute("SELECT id, indicado_por FROM users WHERE email = ?", (email_comprador,))
    comprador = cursor.fetchone()

    if not comprador:
        return jsonify({"error": "Usuário não encontrado"}), 404

    comprador_id, indicado_por = comprador

    # Marca a compra como realizada
    cursor.execute("UPDATE users SET comprou = 1 WHERE id = ?", (comprador_id,))

    # Insere a venda no banco
    cursor.execute("INSERT INTO sales (user_id, valor, data_compra) VALUES (?, ?, datetime('now'))", (comprador_id, valor))

    # Calcula e distribui a comissão até 9 níveis
    nivel = 1
    afiliado_atual = indicado_por
    while afiliado_atual and nivel <= 9:
        # Define percentual de comissão por nível (exemplo)
        percentual_comissao = 0.4 if nivel == 1 else 0.02  # 40% no primeiro nível, 1% nos outros

        valor_comissao = valor * percentual_comissao

        cursor.execute("INSERT INTO commissions (afiliado_id, valor_comissao, nivel, pago, data_compra) VALUES (?, ?, ?, 0, datetime('now'))", 
                       (afiliado_atual, valor_comissao, nivel))

        # Busca o próximo afiliado no nível acima
        cursor.execute("SELECT indicado_por FROM users WHERE id = ?", (afiliado_atual,))
        result = cursor.fetchone()
        afiliado_atual = result[0] if result else None

        nivel += 1

        print(f"Afiliado {afiliado_atual} no nível {nivel}, comissão: {valor_comissao}")
        print(f"Afiliado atual (ID): {afiliado_atual}, próximo afiliado: {result}")


    conn.commit()
    conn.close()

    return jsonify({"success": "Venda processada com sucesso!"}), 200

@app.route("/admin/webhook_logs", methods=["GET"])
def webhook_logs():
    # Verifica se o usuário logado é o dono da plataforma (você)
    if 'user_id' not in session or session.get('user_id') != 1:  # Substitua 1 pelo seu user_id
        return "Acesso negado. Esta área é restrita ao administrador.", 403

    conn = db_connect()
    cursor = conn.cursor()

    # Busca todos os logs de webhooks
    cursor.execute('''
        SELECT wl.id, u.nome, wl.token, wl.dados, wl.data_recebimento 
        FROM webhook_logs wl
        JOIN users u ON wl.user_id = u.id
        ORDER BY wl.data_recebimento DESC
    ''')
    logs = cursor.fetchall()

    conn.close()

    # Passa os logs para o template
    return render_template("webhook_logs.html", logs=logs)






if __name__ == "__main__":
    app.run(debug=True)
