from flask import Flask, request, Response, jsonify
from sqlalchemy.orm import Session
from configuration import Configuration
from models import database, Order, Product, ProductOrder, Category, ProductCategory
from email.utils import parseaddr
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, create_refresh_token, get_jwt_identity, get_jwt
from sqlalchemy import and_, func
from rolePerm import roleCheck
import io
import csv, json
from collections import defaultdict

application = Flask(__name__)
application.config.from_object(Configuration)

jwt = JWTManager(application)

@application.route('/update', methods=['POST'])
@roleCheck(role="vlasnik")
def update():

    file = request.files.get('file')
    if not file:
        return jsonify({"message": "Field file is missing."}), 400

    content = file.stream.read().decode("cp1252")
    stream = io.StringIO(content)
    reader = csv.reader(stream)
    redniBroj = 0
    for row in reader:
        if len(row) != 3:
            message = "Incorrect number of values on line " + str(redniBroj) + "."
            return jsonify({"message": message}), 400
        try:
            price = float(row[2])
            if price <= 0:
                raise ValueError
        except ValueError:
            message = "Incorrect price on line " + str(redniBroj) + "."
            return jsonify({"message": message}), 400

        existing_product = Product.query.filter(Product.name==row[1]).first()
        if existing_product:
            return jsonify({"message": f"Product {row[1]} already exists."}), 400
        redniBroj+=1

    stream.seek(0)
    for row in csv.reader(stream):
        product_name = row[1]
        category_names = row[0].split('|')
        price = float(row[2])

        new_product = Product(name=product_name, price=price)
        database.session.add(new_product)
        database.session.commit()

        for cat_name in category_names:
            category = Category.query.filter(Category.name==cat_name).first()

            if not category:
                category = Category(name=cat_name)
                database.session.add(category)
                database.session.commit()

            product_category_link = ProductCategory(productId=new_product.id, categoryId=category.id)
            database.session.add(product_category_link)
            database.session.commit()

    return Response(status = 200)


@application.route('/product_statistics', methods=['GET'])
@roleCheck(role="vlasnik")
def product_statistics():
    statistics = []

    products = Product.query.all()
    for product in products:
        """sold = Product.query(func.count(Order.product_id)).filter(Order.product_id == product.id,
                                                                  Order.status == 'izvršena').scalar()
        waiting = Product.query(func.count(Order.product_id)).filter(Order.product_id == product.id,
                                                             Order.status == 'čekanja').scalar()"""
        count = func.count(product.id)
        sold = (Product.query.join(ProductOrder, ProductOrder.productId == Product.id)
                .join(Order, ProductOrder.orderId == Order.id)
                .filter(Order.status == "COMPLETE", Product.id == product.id)
                .group_by(Product.id)
                .with_entities(count)
                .scalar())

        waiting = (Product.query.join(ProductOrder, ProductOrder.productId == Product.id)
                   .join(Order, ProductOrder.orderId == Order.id)
                   .filter(Order.status == "CREATED", Product.id == product.id)
                   .group_by(Product.id)
                   .with_entities(count)
                   .scalar())
        if waiting==None: waiting = 0
        if sold == None: sold = 0
        if sold > 0:
            statistics.append({
                "name": product.name,
                "sold": sold,
                "waiting": waiting
            })

    return jsonify({"statistics": statistics}), 200

from collections import defaultdict
from flask import request, jsonify

@application.route('/category_statistics', methods=['GET'])
@roleCheck(role="vlasnik")
def category_statistics():
    header = request.headers.get('Authorization')
    if not header:
        return jsonify({"msg": "Missing Authorization Header"}), 401

    dictionary = defaultdict(int)

    product_orders = ProductOrder.query.join(Product, ProductOrder.productId == Product.id).all()

    for product_order in product_orders:
        for category in product_order.categories:
            dictionary[category.name] += product_order.quantity

    result = sorted(dictionary.keys(), key=lambda x: (-dictionary[x], x))

    return jsonify({"statistics": result}), 200

    """ query = database.session.query(
        Category.name,
        func.sum(ProductOrder.quantity)
    ).join(ProductCategory, ProductCategory.categoryId == Category.id) \
        .join(Product, Product.id == ProductCategory.productId) \
        .join(ProductOrder, ProductOrder.productId == Product.id) \
        .join(Order, ProductOrder.orderId == Order.id) \
        .group_by(Category.name) \
        .order_by(func.sum(ProductOrder.quantity).desc(), Category.name).all()

    result = [name[0] for name in query]

    return jsonify({"statistics": result}), 200"""

if(__name__=="__main__"):
    database.init_app(application)
    application.run(debug = True, port = 5003)


