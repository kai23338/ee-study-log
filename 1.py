import os
import uuid
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from markdown import markdown
from werkzeug.utils import secure_filename # 用于安全处理文件名

# --- 配置部分 ---

app = Flask(__name__)
CORS(app, supports_credentials=True) 

# 1. 数据库配置
# 优先使用环境变量(Render), 本地则使用 SQLite (使用 v2 版本以应用新表结构)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site_v2.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_final_super_secret_key_2025' 

# 2. 文件上传配置
# 图片和视频将保存在 static/uploads 文件夹下
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# 允许上传的扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'avi', 'webm'}
# 限制最大上传大小 (例如 100MB)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# --- 辅助函数 ---

def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """根据扩展名判断是 image 还是 video"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in {'mp4', 'mov', 'avi', 'webm'}:
        return 'video'
    return 'image'

# --- 数据库模型 ---

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(50), nullable=False, default='生活')
    content_markdown = db.Column(db.Text, nullable=True) # 内容可选，因为可能只发图
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # 新增字段：多媒体支持
    media_type = db.Column(db.String(20), nullable=True) # 'image' 或 'video' 或 None
    media_filename = db.Column(db.String(255), nullable=True) # 文件名
    
    def __repr__(self):
        return f"Post('{self.title}', '{self.media_type}')"

# 首次运行时创建表
with app.app_context():
    db.create_all()

# --- 路由逻辑 ---

@app.route('/')
def home():
    """主页：以瀑布流/列表形式显示日志"""
    # 按时间倒序排列
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('index.html', posts=posts)


@app.route('/new', methods=['GET', 'POST'])
def new_post():
    """发布页：支持上传图片、视频和文字"""
    
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            topic = request.form.get('topic')
            content = request.form.get('content')
            
            media_type = None
            media_filename = None

            # --- 处理文件上传 ---
            if 'media_file' in request.files:
                file = request.files['media_file']
                
                if file and file.filename != '' and allowed_file(file.filename):
                    # 1. 生成安全且唯一的文件名 (防止文件名冲突)
                    original_filename = secure_filename(file.filename)
                    file_ext = original_filename.rsplit('.', 1)[1].lower()
                    unique_name = f"{uuid.uuid4().hex[:8]}_{original_filename}"
                    
                    # 2. 保存文件
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                    file.save(save_path)
                    
                    # 3. 记录信息
                    media_filename = unique_name
                    media_type = get_file_type(unique_name)

            # --- 存入数据库 ---
            # 只有当有标题，并且 (有内容 或者 有文件) 时才允许发布
            if title and (content or media_filename):
                new_post = Post(
                    title=title,
                    topic=topic,
                    content_markdown=content,
                    media_type=media_type,
                    media_filename=media_filename
                )
                
                db.session.add(new_post)
                db.session.commit()
                return redirect(url_for('home'))
            
            return render_template('new_post.html', error="请至少填写标题，并输入内容或上传文件。")

        except Exception as e:
            print(f"Error: {e}")
            return render_template('new_post.html', error=f"发布失败: {str(e)}")

    return render_template('new_post.html', error=None)


@app.route('/post/<int:post_id>')
def post_detail(post_id):
    """详情页：展示大图、视频播放器和 Markdown 内容"""
    
    post = db.session.get(Post, post_id)
    if not post:
        from flask import abort
        abort(404)
        
    # 渲染 Markdown 为 HTML
    content_html = markdown(post.content_markdown) if post.content_markdown else ""
    
    return render_template('detail.html', post=post, content_html=content_html)

# --- Gunicorn 入口 ---
# 在生产环境中，Gunicorn 会直接从 app 变量启动，不需要 main 函数

if __name__ == '__main__':
    # 开启 Debug 模式，并运行在 5000 端口
    # host='0.0.0.0' 允许局域网访问
    app.run(host='0.0.0.0', debug=True, port=5000)
