import flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from werkzeug.utils import secure_filename
import os
import random

app = flask.Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SECRET_KEY"] = "websitesisecretkey"
app.config['UPLOAD_FOLDER'] = "profile_pics"

db = SQLAlchemy(app)

bcrypt = Bcrypt(app)

login_manager = LoginManager(app)


class AccountData(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    email = db.Column(db.String, unique=True)
    password = db.Column(db.String)
    fullname = db.Column(db.String)
    bio = db.Column(db.String)
    profile_pic = db.Column(db.String)
    gender = db.Column(db.String)
    owner = db.Column(db.Integer)
    point_average = db.Column(db.Float, default=10)
    followed = db.Column(db.String, default="")


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    content = db.Column(db.String)
    author = db.Column(db.Integer)
    comments = db.Column(db.String, default="")
    image = db.Column(db.String, default="No image")


class MeetingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    place = db.Column(db.String)
    time = db.Column(db.String)
    meeter = db.Column(db.Integer)
    viewed = db.Column(db.Boolean, default=False)
    author = db.Column(db.Integer)
    status = db.Column(db.String, default="Görülmedi")


class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    messages = db.Column(db.String)
    participants = db.Column(db.String)


@login_manager.user_loader
def load_user(user_id):
    return AccountData.query.get(user_id)


@app.route("/return_chat/id=<chat_id>")
@login_required
def returnChat(chat_id):
    messages = ""
    if str(current_user.id) in Chat.query.get(int(chat_id)).participants.split("&&"):
        messages = Chat.query.get(int(chat_id)).messages.split("&&")
    return flask.render_template("return_chat.html", messages=messages)


@app.route("/create_chat/usr=<usr_id>")
@login_required
def createChat(usr_id):
    new_chat = Chat(messages="", participants=str(current_user.id) + "&&" + usr_id)
    db.session.add(new_chat)
    db.session.commit()
    return flask.redirect("/chat/cht=" + str(new_chat.id))


@app.route("/chat/cht=<cht_id>", methods=["POST", "GET"])
@login_required
def chat(cht_id):
    main_chat = {
        "message_to": AccountData.query.get(str(Chat.query.get(int(cht_id)).participants.split("&&")[-1])),
        "chat_id": cht_id
    }

    if flask.request.method == "POST":

        Chat.query.get(int(cht_id)).messages += current_user.fullname + ": " + flask.request.values["message"] + "&&"
        db.session.commit()

        return "Confirmed"

    user = main_chat["message_to"]
    if str(current_user.id) == str(user.id):
        user = AccountData.query.get(str(Chat.query.get(int(cht_id)).participants.split("&&")[0]))

    return flask.render_template("chat.html", main_chat=main_chat, user=user)


@app.route("/search/q=<name>")
def search(name):
    names = AccountData.query.filter(AccountData.fullname.like("%" + name + "%")).all()
    processed_names = []
    for i in names:
        processed_names.append({
            "title": i.fullname,
            "content": i.bio,
            "onclick": "/return_user/usr=" + str(i.id)
        })
    return flask.render_template("search.html", followed_posts=processed_names)


@app.route("/set_meeting/usr=<user_id>", methods=["POST", "GET"])
@login_required
def setMeeting(user_id):
    if flask.request.method == "POST":
        new_meeting = MeetingRequest(place=flask.request.values["place"], time=flask.request.values["time"],
                                     author=current_user.id, meeter=user_id)
        db.session.add(new_meeting)
        db.session.commit()
        return flask.redirect("/home")
    return flask.render_template("meeting.html", user=AccountData.query.get(int(user_id)))


@app.route("/set_meeting_status/mt=<meeting_id>/sts=<new_status>")
@login_required
def set_meeting_status(meeting_id, new_status):
    meeting = MeetingRequest.query.get(meeting_id)

    if not meeting.meeter == current_user.id:
        return flask.redirect("/home")

    meeting.status = new_status
    db.session.commit()

    return flask.redirect("/home")


@app.route("/chats")
@login_required
def viewChats():
    user_chats = []

    for i in Chat.query.all():
        if str(current_user.id) in i.participants.split("&&"):
            if i.participants.split("&&")[0] == str(current_user.id):
                user_chats.append({
                    "user": AccountData.query.get(int(i.participants.split("&&")[-1])),
                    "id": i.id
                })
            else:
                user_chats.append({
                    "user": AccountData.query.get(int(i.participants.split("&&")[0])),
                    "id": i.id
                })

    return flask.render_template("list_chat.html", user_chats=user_chats)


@app.route("/logout")
def logout():
    logout_user()
    return flask.redirect("/")


@app.route("/return_user/usr=<user_id>", methods=["POST", "GET"])
@login_required
def return_user(user_id):
    user_posts = Post.query.filter_by(author=int(user_id))
    is_followed = user_id in current_user.followed
    follow_data = "Follow"
    if is_followed:
        follow_data = "Unfollow"
    if flask.request.method == "POST":
        if not is_followed:
            current_user.followed += user_id + "&&"
            db.session.commit()
        else:
            current_user.followed = current_user.followed.replace(user_id + "&&", "")
            db.session.commit()
        return flask.redirect("/return_user/usr=" + user_id)
    return flask.render_template("user_view.html", user=AccountData.query.get(int(user_id)), user_posts=user_posts,
                                 follow_data=follow_data)


@app.route("/home", methods=["POST", "GET"])
@login_required
def home():
    followed_posts = []
    pending_meetings = []
    final_meetings = []
    all_meetings = []

    recommendations = []

    for i in current_user.followed.split("&&"):
        if not i == "":
            for c in AccountData.query.get(i).followed.split("&&"):
                if c not in current_user.followed.split("&&"):
                    recommendations.append(AccountData.query.get(c))

    if flask.request.method == "POST":
        Post.query.get(int(flask.request.values["post_index"])).comments += current_user.fullname + ": " +\
                                                                            flask.request.values["comment"] + "&&"
        db.session.commit()
        return "Saved"

    for i in MeetingRequest.query.filter_by(meeter=current_user.id).all():
        if not i.viewed:
            pending_meetings.append(i)

    for i in pending_meetings:
        final_meetings.append(
            {
                "requester": AccountData.query.get(i.author).fullname,
                "location": i.place,
                "time": i.time,
                "id": str(i.id)
            }
        )

    for i in MeetingRequest.query.filter_by(meeter=current_user.id).all():
        if i.status == "Görüldü" or not i.viewed:
            all_meetings.append({
                "requester": AccountData.query.get(i.author).fullname,
                "location": i.place,
                "time": i.time,
                "id": str(i.id)
            })

    for i in pending_meetings:
        i.viewed = True
        i.status = "Görüldü"

    db.session.commit()

    for i in current_user.followed.split("&&"):
        if len(i) > 0:
            for c in Post.query.filter_by(author=int(i)).all():
                followed_posts.append({
                    "title": c.title,
                    "content": c.content,
                    "author": AccountData.query.get(c.author).fullname,
                    "comments": c.comments,
                    "id": str(c.id),
                    "image": c.image,
                    "author_id": c.author
                })

    followed_posts.reverse()
    return flask.render_template("home.html", followed_posts=followed_posts, pending_meetings=final_meetings,
                                 all_meetings=all_meetings, recommended=recommendations[:6])


@app.route("/", methods=["POST", "GET"])
def index():
    if current_user.is_authenticated:
        return flask.redirect("/home")
    if flask.request.method == "POST":
        values = flask.request.values
        user = AccountData.query.filter_by(email=values["email"]).first()
        if bcrypt.check_password_hash(user.password, values["password"]):
            login_user(user)
            return flask.redirect("/home")
    return flask.render_template("index.html")


@app.route("/post", methods=["POST", "GET"])
@login_required
def makePost():
    if flask.request.method == "POST":
        new_post = Post(title=flask.request.values["title"], content=flask.request.values["content"],
                        author=current_user.id)

        try:
            file = flask.request.files['image']
            if len(file.filename) > 2:
                filename = str(random.randint(99999999, 999999999)) + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                new_post.image = filename
        except:
            pass

        db.session.add(new_post)
        db.session.commit()
        return flask.redirect("/home")
    return flask.render_template("post.html", user=current_user)


@app.route("/profile")
@login_required
def profile():
    all_meets = MeetingRequest.query.filter_by(author=current_user.id).all()
    meeting_requests = []
    for i in all_meets:
        meeting_requests.append({
            "meeter": AccountData.query.get(i.meeter).fullname,
            "time": i.time,
            "place": i.place,
            "status": i.status
        })
    return flask.render_template("profile.html", user=current_user, meeting_requests=meeting_requests,
                                 user_posts=Post.query.filter_by(author=current_user.id).all())


@app.route("/change_picture", methods=["POST", "GET"])
@login_required
def changePicture():
    if flask.request.method == "POST":
        file = flask.request.files['profile_pic']
        filename = str(random.randint(99999999, 999999999)) + secure_filename(file.filename)

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        current_user.profile_pic = filename
        db.session.commit()
        return flask.redirect("/profile")
    return flask.render_template("change_pic.html")


@app.route("/register", methods=["POST", "GET"])
def register():
    if flask.request.method == "POST":
        values = flask.request.values
        new_user = AccountData(username=values["username"], password=bcrypt.generate_password_hash(values["password"]),
                               email=values["email"], fullname=values["name"] + " " + values["surname"],
                               bio=values["bio"],
                               gender=values["gender"], followed="1&&")
        file = flask.request.files['profile_pic']
        filename = str(random.randint(99999999, 999999999)) + secure_filename(file.filename)

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_user.profile_pic = filename

        db.session.add(new_user)
        db.session.commit()
    return flask.render_template("register.html")


@app.route("/saveBio", methods=["POST", "GET"])
@login_required
def saveBio():
    current_user.bio = flask.request.values["bio"]
    db.session.commit()
    return "Confirmed"


@app.route("/profile_p=<picture_path>")
def profilePic(picture_path):
    return flask.send_file(os.path.join(app.config['UPLOAD_FOLDER'], picture_path))
