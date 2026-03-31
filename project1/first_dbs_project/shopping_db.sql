CREATE DATABASE shopping_db;
USE shopping_db;

CREATE TABLE customer (
    email VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100)
);

CREATE TABLE book (
    ISBN VARCHAR(20) PRIMARY KEY,
    title VARCHAR(100),
    price FLOAT
);

CREATE TABLE warehouse (
    code INT PRIMARY KEY,
    address VARCHAR(100)
);

CREATE TABLE stock (
    ISBN VARCHAR(20),
    warehouse_code INT,
    quantity INT,
    PRIMARY KEY (ISBN, warehouse_code),
    FOREIGN KEY (ISBN) REFERENCES book(ISBN),
    FOREIGN KEY (warehouse_code) REFERENCES warehouse(code)
);

CREATE TABLE shopping_basket (
    basket_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_email VARCHAR(100),
    FOREIGN KEY (customer_email) REFERENCES customer(email)
);

CREATE TABLE basket_items (
    basket_id INT,
    ISBN VARCHAR(20),
    quantity INT,
    PRIMARY KEY (basket_id, ISBN),
    FOREIGN KEY (basket_id) REFERENCES shopping_basket(basket_id),
    FOREIGN KEY (ISBN) REFERENCES book(ISBN)
);

INSERT INTO warehouse VALUES (1, 'Main Warehouse');