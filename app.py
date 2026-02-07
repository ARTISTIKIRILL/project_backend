from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection
from datetime import datetime, timedelta
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
import secrets


app = Flask(__name__)

# Важно: правильная настройка для Flask-Login
app.secret_key = secrets.token_hex(32)

# Критически важные настройки сессии для Flask
app.config.update(
    # Настройки сессии
    SESSION_COOKIE_NAME='session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,    # False для localhost
    SESSION_COOKIE_SAMESITE='Lax',   # 'Lax' для кросс-ориджин запросов
    SESSION_COOKIE_DOMAIN=None,
    SESSION_COOKIE_PATH='/',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    
    # Настройки Flask-Login
    REMEMBER_COOKIE_NAME='remember_token',
    REMEMBER_COOKIE_DURATION=timedelta(days=7),
    REMEMBER_COOKIE_SECURE=False,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='Lax',
    
    # Для защиты от CSRF
    WTF_CSRF_ENABLED=False  # Отключаем если не используем Flask-WTF
)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'signin'  # Имя функции для входа
login_manager.session_protection = "strong"  # Защита сессии

# Настройки CORS с явным указанием origins
CORS(app, 
     supports_credentials=True,
     origins=["http://localhost:5500", "http://127.0.0.1:5500"],
     allow_headers=['Content-Type', 'Authorization', 'Accept'],
     expose_headers=['Content-Type', 'Set-Cookie'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['логин']
        self.name = user_data['имя']
        self.surname = user_data['фамилия']
        self.user_class = user_data['класс']
        self.role = user_data.get('роль', 'user')
        self.study = user_data['учеба']
        self.fun = user_data['развлечения']
        self.health = user_data['здоровье']
        self.points = user_data['количество_очков']

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM Пользователь WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if user_data:
            return User(user_data)
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

@app.route("/get_statistik1", methods=["GET"])
def get_statistik1():
    """Заглушка для тестирования эндпоинта /get_statistik"""
    
    # Фиксированные тестовые данные
    test_data = {
        "user": {
            "id": 12345,
            "name": "Мария",
            "surname": "Петрова",
            "class": "11Б",
            "login": "petrova_maria"
        },
        "level": {
            "current_level": 4,
            "points": 342,
            "cur_level_points": 42,  # 342 % 100 = 42
            "max_level_points": 400,  # 4 * 100 = 400
            "progress_percentage": 42.0,  # (42/100)*100
        }, 
        "stats": {
            "study": 78,
            "fun": 65,
            "health": 92
        }
    }
    
    # Или можно использовать параметры запроса для разных тестовых сценариев
    return jsonify(test_data)


@app.route("/get_statistik", methods=["GET"])
#@login_required
def get_statistik():
    try:
        level = current_user.points // 100 + 1
        max_level_points = level * 100
        cur_level_points = current_user.points % 100

        study = max(0, min(100, current_user.study))
        fun = max(0, min(100, current_user.fun))
        health = max(0, min(100, current_user.health))

        if max_level_points > 0:
            progress_percentage = (cur_level_points / 100) * 100
        else:
            progress_percentage = 0

        return jsonify({
            "user": {
                "id": current_user.id,
                "name": current_user.name,
                "surname": current_user.surname,
                "class": current_user.user_class,
                "login": current_user.username
            },
            "level": {
                "current_level": level,
                "points": current_user.points,
                "cur_level_points": cur_level_points,
                "max_level_points": max_level_points,
                "progress_percentage": progress_percentage, 
            }, 
            "stats": {
                "study": study,
                "fun": fun,
                "health": health
            }
        })
    except Exception as e:
        print(f"Ошибка получения данных о пользователе: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/get_question", methods=["GET"])
#@login_required
def get_question():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT Вопросы.id, Вопросы.дата_создания, Вопросы.текст, Категория.название as категория
            FROM Вопросы
            JOIN Категория ON Вопросы.id_категории = Категория.id
            ORDER BY RAND()
            LIMIT 1
        """)
        question = cursor.fetchone()

        if not question:
            return jsonify({"error": "Вопросы не найдены"}), 404
        
        cursor.execute("""
            SELECT id, текст_ответа, изм_учеба, изм_развлечения, изм_здоровье
            FROM Вариант_ответа
            WHERE id_вопроса = %s
        """, (question['id'],))

        options = cursor.fetchall()

        if not options:
            return jsonify({"error": "Варианты ответа не найдены"}), 404
        
        formatted_options = []
        for i, option in enumerate(options):
            formatted_options.append({
                "id": option['id'],
                "text": option['текст_ответа'],
                "letter": chr(i + 65),
                "effects": {
                    "study": option['изм_учеба'],
                    "fun": option['изм_развлечения'],
                    "health": option['изм_здоровье']
                }
            })
        
        return jsonify({
            "question": {
                "id": question['id'],
                "text": question['текст'],
                "category": question['категория']
            },
            "options": formatted_options
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/submit_answer", methods=["POST"])
@login_required
def submit_answer():
    user_id = current_user.id
    data = request.json

    answer_id = data.get('answer_id')
    question_id = data.get('question_id')
    if not answer_id or not question_id:
        return jsonify({"error": "Заполните все поля"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT изм_учеба, изм_развлечения, изм_здоровье
            FROM Вариант_ответа
            WHERE id = %s AND id_вопроса = %s
        """,(answer_id, question_id))

        answer = cursor.fetchone()

        if not answer:
            return jsonify({"error": "Ответ не найден"}), 404

        points = 20

        cursor.execute("""
            UPDATE Пользователь
            SET количество_очков = количество_очков + %s,
                учеба = учеба + %s,
                развлечения = развлечения + %s,
                здоровье = здоровье + %s
            WHERE id = %s
        """, (points, answer['изм_учеба'], answer['изм_развлечения'], answer['изм_здоровье'], user_id))

        cursor.execute("""
            INSERT INTO Логи_действий
            (дата_события, наименование_действия, Пользователь_id)
            VALUES (%s, %s, %s)
        """, (datetime.now(), "Ответ на вопрос", user_id))

        conn.commit()

        # Обновляем данные пользователя в сессии
        cursor.execute("SELECT * FROM Пользователь WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        login_user(User(user_data))

        return jsonify({
            "message": "Ответ принят",
            "points_earned": points,
            "effects": {
                "study": answer['изм_учеба'],
                "fun": answer['изм_развлечения'],
                "health": answer['изм_здоровье'],
            }
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        cursor.close()
        conn.close()

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json

    login = data.get("login")
    password = data.get("password")
    name = data.get("name")
    surname = data.get("surname")
    user_class = data.get("class")

    if not all([login, password, name, surname, user_class]):
        return jsonify({"error": "Не все поля заполнены"}), 400

    password_hash = generate_password_hash(password)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM Пользователь WHERE логин=%s", (login,))
    if cursor.fetchone():
        return jsonify({"error": "Логин уже существует"}), 409

    cursor.execute("""
        INSERT INTO Пользователь
        (имя, фамилия, класс, логин, хэш_пароля, дата_регистрации,
         количество_очков, учеба, развлечения, здоровье, роль)
        VALUES (%s,%s,%s,%s,%s,%s,0,0,0,0,'user')
    """, (
        name,
        surname,
        user_class,
        login,
        password_hash,
        datetime.now()
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Регистрация успешна"}), 201

@app.route("/signin", methods=["POST"])
def signin():
    data = request.json

    login = data.get("login")
    password = data.get("password")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM Пользователь WHERE логин=%s",
            (login,)
        )
        user_data = cursor.fetchone()

        if not user_data or not check_password_hash(user_data["хэш_пароля"], password):
            return jsonify({"error": "Неверный логин или пароль"}), 401
        
        # Создаем объект пользователя и логиним
        user = User(user_data)
        
        # Важно: установить remember=True для долгоживущей сессии
        login_user(user, remember=True)
        
        print(f"User logged in: {user.id}, {user.username}")
        print(f"User authenticated: {current_user.is_authenticated}")
        
        return jsonify({
            "message": "Успешный вход",
            "user": {
                "id": user.id,
                "name": user.name,
                "surname": user.surname,
                "class": user.user_class,
                "role": user.role,
                "login": user.username,
                "study": user.study,
                "fun": user.fun,
                "health": user.health,
                "points": user.points
            }
        })

    except Exception as e:
        print(f"Error during signin: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/check_auth", methods=["GET"])
def check_auth():
    print(f"Current user: {current_user}")
    print(f"Is authenticated: {current_user.is_authenticated}")
    print(f"User ID: {current_user.get_id() if current_user.is_authenticated else 'None'}")
    
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "name": current_user.name,
                "surname": current_user.surname,
                "class": current_user.user_class,
                "role": current_user.role,
                "login": current_user.username,
                "study": current_user.study,
                "fun": current_user.fun,
                "health": current_user.health,
                "points": current_user.points
            }
        })
    return jsonify({"authenticated": False})

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Вы успешно вышли из аккаунта"})

@app.route("/profile", methods=["GET"])
@login_required
def profile():
    return jsonify({
        "id": current_user.id,
        "name": current_user.name,
        "surname": current_user.surname,
        "class": current_user.user_class,
        "role": current_user.role,
        "login": current_user.username,
        "study": current_user.study,
        "fun": current_user.fun,
        "health": current_user.health,
        "points": current_user.points
    })

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Сервер работает",
        "endpoints": [
            "POST /signin - авторизация",
            "GET /check_auth - проверка авторизации",
            "POST /logout - выход",
            "POST /signup - регистрация",
            "GET /profile - профиль пользователя"
        ]
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)