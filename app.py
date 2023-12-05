import os
import datetime, pytz

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
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


# Define helper function to update portfolio according to buy/sell, returns True if successfull, False if failed
def updateportfolio(userid, transaction, symbol, shares):
    # Detect what type of transaction is being performed
    if transaction == "buy":
        # Check if stock exists in user's portfolio
        if db.execute(
            "SELECT * FROM portfolio WHERE userid = ? AND symbol = ?", userid, symbol
        ):
            count = db.execute(
                "SELECT count FROM portfolio WHERE userid = ? AND symbol = ?",
                userid,
                symbol,
            )
            # Add purchase to count of shares of stock
            count[0]["count"] = count[0]["count"] + shares
            # Update count in db
            db.execute(
                "UPDATE portfolio SET count = ? WHERE userid = ? and symbol = ?",
                count[0]["count"],
                userid,
                symbol,
            )
            return True
        else:
            # Else create the row in the table
            db.execute(
                "INSERT INTO portfolio (userid, symbol, count) VALUES (?, ?, ?)",
                userid,
                symbol,
                shares,
            )
            return True
    elif transaction == "sell":
        # Check if stock exists in user's portfolio
        if db.execute(
            "SELECT * FROM portfolio WHERE userid = ? AND symbol = ?", userid, symbol
        ):
            count = db.execute(
                "SELECT count FROM portfolio WHERE userid = ? AND symbol = ?",
                userid,
                symbol,
            )
            # Check if sell count > then user count
            if count[0]["count"] < shares:
                flash("You do not own enough shares for this transaction")
                return False

            count[0]["count"] = count[0]["count"] - shares
            # Update count in db
            db.execute(
                "UPDATE portfolio SET count = ? WHERE userid = ? and symbol = ?",
                count[0]["count"],
                userid,
                symbol,
            )
            return True
        else:
            # Else user cannot sell a stock he does not own
            flash("You do not own this stock")
            return False
    else:
        flash("Transaction not supported")
        return False


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    userid = session["user_id"]

    # Post method to add cash to account
    if request.method == "POST":
        try:
            # Check if input can cast to an int
            addcash = int(request.form.get("addcash"))
        except ValueError:
            # Catch if user changed input to invalid number
            flash("Not a valid number")
            return redirect("/")

        # Check if user selected an option not in dropdown menu
        if not (addcash == 1000 or addcash == 10000 or addcash == 50000):
            flash("Please select from the drop down menu to add cash")
            return redirect("/")

        # Update cash
        cashrow = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        cash = cashrow[0]["cash"] + addcash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, userid)
        flash("Cash added!")
        return redirect("/")

    # Gather data on user potrfolio
    totalstocks = 0
    portfoliostocks = db.execute(
        "SELECT * FROM portfolio WHERE userid = ? AND NOT count = 0", userid
    )
    for row in portfoliostocks:
        stock = lookup(row["symbol"])
        stockprice = stock["price"]
        stocktotal = stockprice * row["count"]
        totalstocks += stocktotal
        row["stockprice"] = usd(stockprice)
        row["stocktotal"] = usd(stocktotal)

    cashrow = db.execute("SELECT cash FROM users WHERE id = ?", userid)
    cash = cashrow[0]["cash"]
    total = cash + totalstocks

    return render_template(
        "index.html", portfoliostocks=portfoliostocks, cash=usd(cash), total=usd(total)
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Get symbol and shares from form
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        # Check for invalid inputs
        if not symbol:
            flash("Please input a symbol to buy shares")
            return redirect("/buy", code=400)
        stock = lookup(symbol)
        if stock == None:
            flash("Invalid symbol")
            return redirect("/buy", code=400)
        try:
            if not (shares.isnumeric() and int(shares) > 0):
                flash("Please input a whole number of shares greater than 0")
                return redirect("/buy", code=400)
        except ValueError:
            flash("Not a valid number")
            return redirect("/buy", code=400)

        # Get user cash
        userid = session["user_id"]
        budget = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        cost = round(float(stock["price"] * int(shares)), 2)

        # Check funds
        if cost > budget[0]["cash"]:
            flash("Insufficient funds")
            return redirect("/buy", code=400)

        # Use local timezone if possible
        try:
            timezn = os.environ["TZ"]
            timestamp = datetime.datetime.now(pytz.timezone(timezn))
        except KeyError:
            # If key error from 'TZ', use US east
            timestamp = datetime.datetime.now(pytz.timezone("US/Eastern"))
            db.execute(
                "INSERT INTO transactions (time, userid, type, stock, shares, cost) VALUES (?, ?, ?, ?, ?, ?)",
                timestamp,
                userid,
                "buy",
                symbol,
                shares,
                cost,
            )
            budget[0]["cash"] = round(float(budget[0]["cash"] - cost), 2)
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?", budget[0]["cash"], userid
            )
            flash("Purchase successful")
            updateportfolio(userid, "buy", symbol, int(shares))
            return redirect("/")

        db.execute(
            "INSERT INTO transactions (time, userid, type, stock, shares, cost) VALUES (?, ?, ?, ?, ?, ?)",
            timestamp,
            userid,
            "buy",
            symbol,
            shares,
            cost,
        )
        budget[0]["cash"] = round(float(budget[0]["cash"] - cost), 2)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", budget[0]["cash"], userid)
        flash("Purchase successful")
        updateportfolio(userid, "buy", symbol, int(shares))
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userid = session["user_id"]
    transactions = db.execute(
        "SELECT * FROM transactions WHERE userid = ? ORDER BY time DESC, cost", userid
    )
    for transaction in transactions:
        transaction["cost"] = usd(transaction["cost"])
        transaction["type"] = str(transaction["type"]).upper()
        if transaction["type"] == "SELL":
            transaction["shares"] *= -1
    return render_template("history.html", transactions=transactions)


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
        session["username"] = rows[0]["username"]

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
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        if not symbol:
            flash("Please submit a stock's symbol to quote")
            return redirect("/quote", code=400)

        quote = lookup(symbol)
        if quote == None:
            flash("Invalid symbol, try again")
            return redirect("/quote", code=400)

        return render_template("quoted.html", quote=quote, price=usd(quote["price"]))

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        cpassword = request.form.get("confirmation")

        if not (username and password and cpassword == password):
            if username:
                flash("Registration unsuccessful, passwords do not match")
                return redirect("/register", code=400)
            else:
                flash("Registration unsuccessful, invalid username")
                return redirect("/register", code=400)

        if db.execute("SELECT username FROM users WHERE username = ?", username):
            flash("Username already in use")
            return redirect("/register", code=400)

        passhash = generate_password_hash(password)

        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)", username, passhash
        )

        # Query database for registered username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    userid = session["user_id"]
    if request.method == "POST":
        # Get symbol and shares from form
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            flash("Please input a symbol to sell shares")
            return redirect("/sell", code=400)
        stock = lookup(symbol)
        if stock == None:
            flash("Invalid symbol")
            return redirect("/sell", code=400)
        try:
            if not (shares.isnumeric() and int(shares) > 0):
                flash("Please input a number of shares greater than 0")
                return redirect("/sell", code=400)
        except ValueError:
            flash("Not a valid number")
            return redirect("/sell", code=400)

        # If portfolio update unsuccessfull, sell transaction has failed
        if not updateportfolio(userid, "sell", symbol, int(shares)):
            return redirect("/sell", code=400)

        price = round(float(stock["price"] * int(shares)), 2)
        cashrow = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        cash = cashrow[0]["cash"]

        try:
            timezn = os.environ["TZ"]
            timestamp = datetime.datetime.now(pytz.timezone(timezn))
        except KeyError:
            timestamp = datetime.datetime.now(pytz.timezone("US/Eastern"))
            db.execute(
                "INSERT INTO transactions (time, userid, type, stock, shares, cost) VALUES (?, ?, ?, ?, ?, ?)",
                timestamp,
                userid,
                "sell",
                symbol,
                shares,
                price,
            )
            cash = round(float(cash + price), 2)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, userid)
            flash("Sold!")
            return redirect("/")

        db.execute(
            "INSERT INTO transactions (time, userid, type, stock, shares, cost) VALUES (?, ?, ?, ?, ?, ?)",
            timestamp,
            userid,
            "sell",
            symbol,
            shares,
            price,
        )
        cash = round(float(cash + price), 2)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, userid)
        flash("Sold!")
        return redirect("/")

    portfoliostocks = db.execute(
        "SELECT symbol FROM portfolio WHERE userid = ? AND NOT count = 0", userid
    )
    return render_template("sell.html", portfoliostocks=portfoliostocks)

if __name__ == '__main__':
    app.run(debug=True)