from flask import Flask, request
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from requests import get
from passlib.hash import pbkdf2_sha512
#lib

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
api = Api(app)
db = SQLAlchemy(app)

# Model representing the Car table in the database
class CarModel(db.Model):
    __tablename__ = 'cars'
    id = db.Column(db.Integer, primary_key=True)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))

    def json(self):
        return {'id': self.id, 'license_plate': self.license_plate, 'driver_id': self.driver_id}

    @classmethod
    def find_by_attribute(cls, **kwargs):
        return cls.query.filter_by(**kwargs).first()

# Model representing the Driver table in the database
class DriverModel(db.Model):
    __tablename__ = 'drivers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    def json(self):
        return {'id': self.id, 'name': self.name}

    @classmethod
    def find_by_attribute(cls, **kwargs):
        return cls.query.filter_by(**kwargs).first()

# Model representing the Position table in the database
class PositionModel(db.Model):
    __tablename__ = 'positions'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    address = db.Column(db.String(300))

    def json(self):
        return {
            'id': self.id,
            'car_id': self.car_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'date': self.date.isoformat(),
            'address': self.address
        }

    def resolve_address(self):
        # Use the Nominatim API to get the address based on GPS coordinates
        url = f"https://nominatim.org/search?q={self.latitude}+{self.longitude}&format=json"
        response = get(url).json()
        if response:
            self.address = response[0].get('display_name', '')
        else:
            self.address = ''

# Resource for managing individual cars
class Car(Resource):
    def get(self, plate):
        car = CarModel.find_by_attribute(license_plate=plate)
        if car:
            return car.json()
        return {'message': 'Car not found'}, 404

    def post(self, plate):
        if CarModel.find_by_attribute(license_plate=plate):
            return {'message': 'Car already exists'}, 400

        data = request.get_json()
        driver_id = data.get('driver_id')

        if driver_id and not DriverModel.find_by_attribute(id=driver_id):
            return {'message': 'Driver not found'}, 400

        car = CarModel(license_plate=plate, driver_id=driver_id)
        db.session.add(car)
        db.session.commit()
        return car.json(), 201

    def put(self, plate):
        data = request.get_json()
        driver_id = data.get('driver_id')

        car = CarModel.find_by_attribute(license_plate=plate)
        if not car:
            return {'message': 'Car not found'}, 404

        if driver_id and not DriverModel.find_by_attribute(id=driver_id):
            return {'message': 'Driver not found'}, 400

        car.driver_id = driver_id
        db.session.commit()
        return car.json()

    def delete(self, plate):
        car = CarModel.find_by_attribute(license_plate=plate)
        if not car:
            return {'message': 'Car not found'}, 404

        db.session.delete(car)
        db.session.commit()
        return {'message': 'Car deleted'}

# Resource for managing the list of cars
class CarList(Resource):
    def get(self):
        cars = [car.json() for car in CarModel.query.all()]
        return {'cars': cars}

# Resource for managing car positions
class CarPosition(Resource):
    def post(self, plate):
        car = CarModel.find_by_attribute(license_plate=plate)
        if not car:
            return {'message': 'Car not found'}, 404

        data = request.get_json()
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not isinstance(latitude, float) or not isinstance(longitude, float):
            return {'message': 'Invalid latitude or longitude'}, 400

        car_position = PositionModel(car_id=car.id, latitude=latitude, longitude=longitude, date=datetime.now())
        car_position.resolve_address()

        db.session.add(car_position)
        db.session.commit()
        return {'message': 'Position saved'}, 201

# Resource for getting car positions
class CarPositions(Resource):
    def get(self, plate):
        car = CarModel.find_by_attribute(license_plate=plate)
        if not car:
            return {'message': 'Car not found'}, 404

        positions = [position.json() for position in PositionModel.query.filter_by(car_id=car.id).all()]
        return {'positions': positions}

# Resource for assigning a driver to a car
class AssignDriver(Resource):
    def post(self, plate, driver_id):
        car = CarModel.find_by_attribute(license_plate=plate)
        if not car:
            return {'message': 'Car not found'}, 404

        driver = DriverModel.find_by_attribute(id=driver_id)
        if not driver:
            return {'message': 'Driver not found'}, 404

        car.driver_id = driver_id
        db.session.commit()
        return {'message': 'Driver assigned'}

    def delete(self, plate, driver_id):
        car = CarModel.find_by_attribute(license_plate=plate)
        if not car:
            return {'message': 'Car not found'}, 404

        if car.driver_id != driver_id:
            return {'message': 'This assignment does not exist'}, 404

        car.driver_id = None
        db.session.commit()
        return {'message': 'Driver assignment deleted'}

# API endpoints configuration
api.add_resource(CarList, '/cars')
api.add_resource(Car, '/car/<string:plate>')
api.add_resource(CarPosition, '/car/<string:plate>/position')
api.add_resource(CarPositions, '/car/<string:plate>/positions')
api.add_resource(AssignDriver, '/car/<string:plate>/driver/<int:driver_id>')

if __name__ == '__main__':
    db.init_app(app)
    app.run(debug=True)
