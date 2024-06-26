import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    portfolio = db.execute(
        "SELECT stock, SUM(shares) AS total_shares FROM portfolio WHERE userid = ? GROUP BY stock ORDER BY stock", session[
            "user_id"]
    )
    cash = db.execute(
        "SELECT cash FROM users WHERE id = ?", session["user_id"]
    )[0]["cash"]
    # Initialize portfolio total
    total = cash

    # update portfolio to include current stock price
    for stock in portfolio:
        stock['price'] = lookup(stock['stock'])['price']
        stock['value'] = stock['total_shares'] * stock['price']
        total += stock['value']

    return render_template("index.html", portfolio=portfolio, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)
        if not request.form.get("shares"):
            return apology("must provide number of shares to buy", 400)

        # lookup stock
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        quote = lookup(symbol)

        if not quote:
            return apology("stock symbol does not exist", 400)

        # set price and shares requested variables
        price = quote['price']
        shares = request.form.get("shares")
        if shares.isdigit() == False:
            return apology("please enter an integer", 400)
        else:
            shares = int(shares)

        total_price = price * shares
        # get available cash
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", session["user_id"]
        )[0]["cash"]

        # if transaction is valid
        if cash >= total_price:
            cash = cash - total_price
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"]
            )
            portfolio = db.execute(
                "SELECT stock, shares FROM portfolio WHERE userid = ?", session["user_id"]
            )

            stock_to_buy = db.execute(
                "SELECT stock FROM portfolio WHERE stock = ? AND userid = ?", symbol, session["user_id"]
            )
            if not stock_to_buy:
                db.execute(
                    "INSERT INTO portfolio (userid, stock, shares) VALUES (?,?,?)", session[
                        "user_id"], symbol, shares
                )
            else:
                stock = portfolio[0]["stock"]
                existing_shares = portfolio[0]["shares"]
                new_shares = shares + existing_shares
                db.execute(
                    "UPDATE portfolio SET shares = ? WHERE stock = ? AND userid = ?", new_shares, stock, session[
                        "user_id"]
                )
            db.execute(
                "INSERT INTO history (userid, stock, price, shares, type, date) VALUES (?,?,?,?,?,?)", session[
                    "user_id"], symbol, price, shares, "buy", date
            )

        # send user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    history = db.execute(
        "SELECT date, shares, price, type, stock FROM history WHERE userid = ?", session["user_id"]
    )
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)

        # lookup stock
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        quote = lookup(symbol)

        if not quote:
            return apology("stock symbol does not exist", 400)
        # send user to quoted page
        return render_template("quoted.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Check that password and confirmation match
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if password != confirmation:
            return apology("passwords do not match", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username does not exist
        if len(rows) == 1:
            return apology("username already exists", 400)
        elif len(rows) == 0:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?,?)", request.form.get(
                    "username"), generate_password_hash(password)
            )

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)

        # lookup stock
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        quote = lookup(symbol)

        if not quote:
            return apology("stock symbol does not exist", 400)

        # set price and shares requested variables
        price = quote['price']
        shares = int(request.form.get("shares"))

        total_price = price * shares

        # get available cash
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", session["user_id"]
        )[0]["cash"]

        # get available shares
        available_shares = db.execute(
            "SELECT shares FROM portfolio WHERE stock = ? AND userid = ?", symbol, session["user_id"]
        )[0]["shares"]

        # if transaction is valid
        if available_shares >= shares:
            cash += total_price
            new_shares = int(available_shares - shares)
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"]
            )
            db.execute(
                "UPDATE portfolio SET shares = ? WHERE userid = ? AND stock = ?", session[
                    "user_id"], symbol, new_shares
            )
            db.execute(
                "INSERT INTO history (userid, stock, price, shares, type, date) VALUES (?,?,?,?,?,?)", session[
                    "user_id"], symbol, price, shares, "sell", date
            )
        else:
            return apology("not enough shares to sell", 400)

        # send user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        portfolio = db.execute(
            "SELECT DISTINCT stock FROM portfolio WHERE userid = ?", session["user_id"]
        )
        return render_template("sell.html", portfolio=portfolio)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        # Initial value checks including minimum deposit amt
        if not request.form.get('deposit'):
            return apology("must provide numeric value to deposit", 400)
        elif request.form.get('deposit').isnumeric() == False:
            return apology("must provide numeric value to deposit", 400)
        elif float(request.form.get('deposit')) < 100:
            return apology("minimum deposit $100", 400)

        # Get existing cash
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", session["user_id"]
        )[0]["cash"]
        # Get user input for deposit
        deposit = float(request.form.get('deposit'))
        # New cash amount
        cash += deposit
        # Update db with new cash amt
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"]
        )
        return render_template("index.html")
    # handles GET method
    else:
        return render_template("deposit.html")
