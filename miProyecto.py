from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta 
from sqlalchemy import func
import os

app = Flask(__name__)

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
url = os.getenv('DATABASE_URL')

if url and url.startswith("mysql://"):
    url = url.replace("mysql://", "mysql+mysqlconnector://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id_usuarios = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False)

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id_categoria = db.Column(db.Integer, primary_key=True)
    nombre_cat = db.Column(db.String(50), nullable=False)
    productos = db.relationship('Producto', backref='categoria_rel', lazy=True)

class Producto(db.Model):
    __tablename__ = 'productos'
    id_producto = db.Column(db.Integer, primary_key=True)
    nombre_prod = db.Column(db.String(100), nullable=False)
    id_categoria = db.Column(db.Integer, db.ForeignKey('categorias.id_categoria'), nullable=False)

class Material(db.Model):
    __tablename__ = 'materiales'
    id_material = db.Column(db.Integer, primary_key=True) 
    nombre_mat = db.Column(db.String(100))
    stock_actual = db.Column(db.Integer)
    stock_minimo = db.Column(db.Integer)
    id_categoria = db.Column(db.Integer, db.ForeignKey('categorias.id_categoria'))
    id_producto = db.Column(db.Integer, db.ForeignKey('productos.id_producto'))
    talla = db.Column(db.String(10))
    color = db.Column(db.String(20))

class Movimiento(db.Model):
    __tablename__ = 'movimientos'
    id_mov = db.Column(db.Integer, primary_key=True)
    id_material = db.Column(db.Integer, db.ForeignKey('materiales.id_material'))
    tipo_mov = db.Column(db.String(10)) 
    cantidad = db.Column(db.Integer)
    fecha = db.Column(db.DateTime, default=lambda: datetime.utcnow() - timedelta(hours=6))
    id_usuario = db.Column(db.Integer)

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    usuario_ingresado = request.form.get('usuario')
    password_ingresada = request.form.get('password')
    
    user = Usuario.query.filter_by(nombre_usuario=usuario_ingresado).first()

    if user and user.password == password_ingresada:
        alertas_reales = Material.query.filter(Material.stock_actual <= Material.stock_minimo).all()
        
        movimientos_recientes = db.session.query(Movimiento, Material)\
            .join(Material, Movimiento.id_material == Material.id_material)\
            .order_by(Movimiento.fecha.desc()).limit(5).all()
        
        return render_template('dashboard.html', 
                            usuario=user.nombre_usuario, 
                            alertas=alertas_reales,
                            movimientos=movimientos_recientes)
    else:
        return "<h1>Error: Usuario o contraseña incorrectos</h1><a href='/'>Volver a intentar</a>"

@app.route('/categoria/textiles')
def ver_textiles():
    productos_textiles = Producto.query.filter_by(id_categoria=1).all()
    materiales = Material.query.filter_by(id_categoria=1).all()
    return render_template('textiles.html', productos=productos_textiles, materiales=materiales)

@app.route('/catalogo')
def gestion_catalogo():
    lista_productos = Producto.query.all()
    return render_template('catalogo.html', productos=lista_productos)

@app.route('/catalogo/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if request.method == 'POST':
        nombre = request.form.get('nombre_producto')
        id_cat = request.form.get('categoria')
        stock_min = request.form.get('stock_minimo')
        tallas_seleccionadas = request.form.getlist('tallas')
        colores_seleccionados = request.form.getlist('colores')
        
        try:
            nuevo_prod = Producto(nombre_prod=nombre, id_categoria=id_cat)
            db.session.add(nuevo_prod)
            db.session.flush()
            
            for color in colores_seleccionados:
                for talla in tallas_seleccionadas:
                    nueva_variante = Material(
                        nombre_mat=f"{nombre} - {color} - {talla}",
                        stock_actual=0,
                        stock_minimo=stock_min,
                        id_categoria=id_cat,
                        id_producto=nuevo_prod.id_producto,
                        talla=talla,
                        color=color
                    )
                    db.session.add(nueva_variante)
            db.session.commit()
            return redirect(url_for('gestion_catalogo'))
        except Exception as e:
            db.session.rollback()
            return f"Error: {e}"
    return render_template('nuevo_producto.html')

@app.route('/catalogo/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    producto = Producto.query.get(id)
    if request.method == 'POST':
        producto.nombre_prod = request.form.get('nombre_producto')
        producto.id_categoria = request.form.get('categoria')
        try:
            db.session.commit()
            return redirect(url_for('gestion_catalogo'))
        except Exception as e:
            db.session.rollback()
            return f"Error al editar: {e}"
    return render_template('editar_producto.html', producto=producto)

@app.route('/catalogo/borrar/<int:id>', methods=['POST'])
def borrar_producto(id):
    try:
        variantes = Material.query.filter_by(id_producto=id).all()
        
        for v in variantes:
            Movimiento.query.filter_by(id_material=v.id_material).delete()
        
        Material.query.filter_by(id_producto=id).delete()
        
        producto = Producto.query.get(id)
        if producto:
            db.session.delete(producto)
            
        db.session.commit()
        return redirect(url_for('gestion_catalogo'))
    except Exception as e:
        db.session.rollback()
        return f"Error al borrar: {e}"

@app.route('/inventario')
def menu_inventario():
    return render_template('inventario_menu.html')

@app.route('/dashboard')
def ir_dashboard():
    alertas_reales = Material.query.filter(Material.stock_actual <= Material.stock_minimo).all()
    
    movimientos_recientes = db.session.query(Movimiento, Material)\
        .join(Material, Movimiento.id_material == Material.id_material)\
        .order_by(Movimiento.fecha.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                           usuario="Pablo", 
                           alertas=alertas_reales,
                           movimientos=movimientos_recientes)

@app.route('/categoria/ceramicos')
def ver_ceramicos():
    productos_ceramicos = Producto.query.filter_by(id_categoria=2).all()
    materiales = Material.query.filter_by(id_categoria=2).all()
    return render_template('ceramicos.html', productos=productos_ceramicos, materiales=materiales)

@app.route('/categoria/viniles')
def ver_viniles():
    productos_viniles = Producto.query.filter_by(id_categoria=3).all()
    materiales = Material.query.filter_by(id_categoria=3).all()
    return render_template('viniles.html', productos=productos_viniles, materiales=materiales)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)