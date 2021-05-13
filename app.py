from datetime import datetime
from collections import namedtuple
from flask import Flask, request, render_template, url_for, redirect, flash
from flask_login import LoginManager, UserMixin, login_required, login_user, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SECRET_KEY'] = 'a really long secret key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///task_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Для отключения после создания бызы
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth'


@login_manager.user_loader
def load_user(id_user):
    return db.session.query(User).get(id_user)


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(100), nullable=False)
    tasks = db.relationship('Tasks', backref='user')

    def __repr__(self):
        return "<{}:{}>".format(self.id, self.login)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Tasks(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(300), nullable=False)
    id_user = db.Column(db.Integer(), db.ForeignKey('user.id'))
    data_create = db.Column(db.DateTime, default=datetime.utcnow)
    changes = db.relationship('Changes', backref='tasks')
    lost_status = db.Column(db.Integer(), db.ForeignKey('status.id'))
    data_updated = db.Column(db.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return "<Tasks {}>".format(self.id)


class Status(db.Model):
    __tablename__ = 'status'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    changes = db.relationship('Changes', backref='status')
    tasks = db.relationship('Tasks', backref='status')

    def __repr__(self):
        return "<Status {}: {}>".format(self.id, self.name)


class Changes(db.Model):
    __tablename__ = 'changes'
    id = db.Column(db.Integer, primary_key=True)
    id_task = db.Column(db.Integer(), db.ForeignKey('tasks.id'))
    id_status = db.Column(db.Integer(), db.ForeignKey('status.id'))
    data_change = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return "<Change {}: {}>".format(self.id, self.id_status)


@app.route("/", methods=['POST', 'GET'])
@app.route("/auth", methods=['POST', 'GET'])
def auth():
    if request.method == "POST":
        login = request.form['login']
        password = request.form['password']
        remember = True if request.form.get('remember_me') else False
        u_auth = User.query.filter_by(login=login).first()
        if not u_auth or not u_auth.check_password(password):
            flash('Пожалуйста, проверьте свои данные для входа и попробуйте еще раз.')
            return redirect(url_for('auth'))
        login_user(u_auth, remember=remember)
        return redirect('/open_tasks')
    else:
        return render_template("auth.html")


@app.route("/open_tasks")
@login_required
def open_tasks():
    tasks = Tasks.query.filter_by(lost_status=1).order_by(Tasks.data_create.desc()).all()
    return render_template("open_tasks.html", tasks=tasks, users=User, status=Status)


@app.route("/create-task", methods=['POST', 'GET'])
@login_required
def create_task():
    if request.method == "POST":
        description = request.form['description']
        id_users = request.form['user']
        task = Tasks(description=description, id_user=id_users, lost_status=1)
        db.session.add(task)
        db.session.commit()
        change = Changes(id_task=task.id, id_status=task.lost_status)
        db.session.add(change)
        db.session.commit()
        return redirect('/open_tasks')
    else:
        users = User.query.all()
        return render_template("create-task.html", users=users)


@app.route("/task/<int:id>/to_work")
@login_required
def to_work_task(id):
    task = Tasks.query.get(id)
    task.lost_status = 2
    db.session.commit()
    change = Changes(id_task=task.id, id_status=task.lost_status)
    db.session.add(change)
    db.session.commit()
    return redirect('/open_tasks')


@app.route("/task/<int:id>/reject")
@login_required
def reject_task(id):
    task = Tasks.query.get(id)
    task.lost_status = 3
    db.session.commit()
    change = Changes(id_task=task.id, id_status=task.lost_status)
    db.session.add(change)
    db.session.commit()
    return redirect('/open_tasks')


@app.route("/works/<int:id>/reject")
@login_required
def reject_works(id):
    task = Tasks.query.get(id)
    task.lost_status = 3
    db.session.commit()
    change = Changes(id_task=task.id, id_status=task.lost_status)
    db.session.add(change)
    db.session.commit()
    return redirect('/to-works')


@app.route("/task/<int:id>/done")
@login_required
def done_task(id):
    task = Tasks.query.get(id)
    task.lost_status = 4
    db.session.commit()
    change = Changes(id_task=task.id, id_status=task.lost_status)
    db.session.add(change)
    db.session.commit()
    return redirect('/to-works')


@app.route("/to-works")
@login_required
def to_works():
    tasks = Tasks.query.filter_by(lost_status=2).order_by(Tasks.data_create.desc()).all()
    return render_template("works_tasks.html", tasks=tasks, users=User, status=Status)


@app.route("/arh-tasks")
@login_required
def arh_tasks():
    tasks = Tasks.query.filter(or_(Tasks.lost_status == 3, Tasks.lost_status == 4)) \
        .order_by(Tasks.data_create.desc()).all()
    return render_template("arh_tasks.html", tasks=tasks, users=User, status=Status)


def normalize_seconds(seconds: int):
    (days, remainder) = divmod(seconds, 86400)
    (hours, remainder) = divmod(remainder, 3600)
    (minutes, seconds) = divmod(remainder, 60)
    return namedtuple("_", ("days", "hours", "minutes", "seconds"))(int(days), int(hours), int(minutes), int(seconds))


@app.route("/stat")
@login_required
def stat():
    stat_dic = {}
    for el in Status.query.all():
        stat_dic[el.name] = len(Tasks.query.filter_by(lost_status=el.id).all())
        if el.id == 4:
            t_list = []
            for task in Tasks.query.filter_by(lost_status=el.id).all():
                work_time = task.data_updated - task.data_create
                t_list.append(work_time.total_seconds())
            sec = sum(t_list) / max(len(t_list), 1)
            norm_date = normalize_seconds(sec)
            data_str = ("{} д. ".format(norm_date.days) if norm_date.days > 0 else "") + \
                       ("{} чac. ".format(norm_date.hours) if norm_date.hours > 0 else "") + \
                       ("{} мин. ".format(norm_date.minutes) if norm_date.minutes > 0 else "") + \
                       ("{} сек. ".format(norm_date.seconds) if norm_date.seconds > 0 else "")
            stat_dic["Среднее время выполнения"] = data_str

    return render_template("statistics.html", stat_dic=stat_dic, users=User)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth'))


if __name__ == "__main__":
    app.run(debug=False)
