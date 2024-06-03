
from flask import Flask, request, jsonify, render_template, redirect
import sqlite3
from datetime import datetime
import json
import shutil

API_KEY = "i0l765RJ30f9HR47L072c2tc74V1597h"

app = Flask(__name__)

conn = sqlite3.connect(f"{"" if True else "db_backup/"}database.db", check_same_thread=False)
cur = conn.cursor()


@app.before_request
def before_request():
    check_db_backup()


@app.route("/")
def index():
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables_list = [row[0] for row in cur.fetchall()]

    all_tables = {}
    hidden_count = 0

    for tablename in all_tables_list:
        # Step 3: Check if we can access 'tables_register' and its content
        cur.execute("SELECT hidden FROM tables_register WHERE name = ?", (tablename,))
        hidden = cur.fetchone()[0] == 1

        if hidden:
            hidden_count += 1
        else:
            cur.execute(f"SELECT COUNT(*) FROM {tablename}")
            row_count = cur.fetchone()[0]

            cur.execute(f"PRAGMA table_info({tablename})")
            rows = cur.fetchall()

            all_tables.update({
                tablename: {
                    "row_count": row_count,
                    "rows": rows
                }
            })

    return render_template("index.html", tables=all_tables, hidden_count=hidden_count)


@app.route("/tables", methods=["GET", "POST"])
def tables():
    error = ""

    if request.method == "POST":
        action, tablename = request.form.get("action").split("-")
        try:
            if action == "delt":
                cur.execute(f"DROP TABLE {tablename}")
            elif action == "drop":
                cur.execute(f"DELETE FROM {tablename}")
            elif action == "edit":
                return redirect(f"/tables/edit/{tablename}")

            conn.commit()
        except sqlite3.Error as e:
            error = f"sqlite3.Error: {str(e)}"

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables_list = [row[0] for row in cur.fetchall()]

    all_tables = {}

    for tablename in all_tables_list:
        # check if the table is sqlite table
        if tablename.startswith("sqlite_"):
            all_tables.update({tablename: False})
        elif tablename == "tables_register":
            all_tables.update({tablename: False})
        else:
            all_tables.update({tablename: True})

    return render_template("tables.html", all_tables=all_tables)


@app.route("/tables/new", methods=["GET", "POST"])
def new_table():
    error = None
    if request.method == "POST":
        tablename = request.form.get("table-name")
        hidden = 1 if request.form.get("hidden") else 0

        cols_str = ""

        for key in request.form:
            if key.startswith("column-name"):
                column_id = key.split("-")[2]

                col_name = request.form.get(f"column-name-{column_id}")
                col_type = request.form.get(f"column-type-{column_id}")
                col_not_null = request.form.get(f"column-notnull-{column_id}")
                col_default = request.form.get(f"column-default-{column_id}")
                col_other = request.form.get(f"column-other-{column_id}")
                col_pk = request.form.get(f"column-pk-{column_id}")

                if col_not_null:
                    col_not_null = " NOT NULL"
                else:
                    col_not_null = ""

                if col_default:
                    col_default = f" DEFAULT {col_default}"
                else:
                    col_default = ""

                if col_other:
                    col_other = f" {col_other}"
                else:
                    col_other = ""

                if col_pk:
                    col_pk = " PRIMARY KEY"
                else:
                    col_pk = ""

                cols_str += f"{col_name} {col_type}{col_not_null}{col_default}{col_other}{col_pk}, "

        if len(cols_str) > 2:
            cols_str = cols_str[:-2]

        query = f"CREATE TABLE {tablename} ({cols_str})"
        try:
            cur.execute(query)
            conn.commit()
        except sqlite3.Error as e:
            error = f"sqlite3.Error: {str(e)}"
        else:
            try:
                cur.execute("INSERT INTO tables_register (name, created_from_ip, created_from_agent, hidden) VALUES (?, ?, ?, ?)", (tablename, str(request.remote_addr), str(request.user_agent), hidden))
                conn.commit()
            except sqlite3.Error as e:
                error = f"sqlite3.Error: {str(e)}"

    return render_template("new-table.html", error=error)


@app.route("/tables/edit/<tablename>", methods=["GET", "POST"])
def edit_table(tablename):
    if request.method == "POST":
        action, column = request.form.get("action").split("-")
        try:
            if action == "delt":
                cur.execute(f"ALTER TABLE {tablename} DROP COLUMN {column}")
            elif action == "drop":
                cur.execute(f"DELETE FROM {tablename}")
            elif action == "edit":
                return redirect(f"/table/edit/{tablename}/{column}")

            conn.commit()
        except sqlite3.Error as e:
            error = f"sqlite3.Error: {str(e)}"

    cur.execute(f"PRAGMA table_info({tablename})")
    columns = cur.fetchall()

    return render_template("edit-table.html", tablename=tablename, columns=columns)


@app.route("/table/<tablename>", methods=["GET", "POST"])
def table(tablename):
    show = True
    message = ""
    data = ""
    column_names = ""

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [row[0] for row in cur.fetchall()]

    selection = "*"
    table = tablename
    other = ""

    if request.method == "POST":
        selection = request.form.get("selection")
        table = request.form.get("table")
        other = request.form.get("other")

    try:
        query = f"SELECT {selection} FROM {table} {other}"
        cur.execute(query)
        data = cur.fetchall()
    except sqlite3.Error as e:
        message = f"Error: {str(e)}"
        show = False
    else:
        if selection == "*":
            cur.execute(f"PRAGMA table_info({table})")
            columns_info = cur.fetchall()
            column_names = [info[1] for info in columns_info]
        else:
            column_names_list = selection.split(",")
            column_names = [str(val).strip() for val in column_names_list]

    if tablename != table:
        return redirect(f"/table/{table}")

    return render_template("table.html", show=show, selection=selection, table=table, other=other, column_names=column_names, data=data, all_tables=all_tables, message=message)


@app.route("/query", methods=["GET", "POST"])
def query():
    message = ""
    data = ""

    if request.method == "POST":
        user_query = request.form.get("query")
        try:
            cur.execute(user_query)
            data = cur.fetchall()
        except sqlite3.Error as e:
            message = f"Error: {str(e)}"

    return render_template("query.html", message=message, data=data)


@app.route("/post/reset/database")
def reset_database():
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cur.fetchall()

        for table in tables:
            table_name = table[0]
            cur.execute(f"DROP TABLE IF EXISTS {table_name};")
            print(f"Dropped table: {table_name}")

        cur.execute("CREATE TABLE tables_register (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_from_ip TEXT NOT NULL, created_from_agent TEXT NOT NULL, hidden BOOL NOT NULL DEFAULT 0, date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        cur.execute("INSERT INTO tables_register (name, created_from_ip, created_from_agent) VALUES (?, ?, ?)", ("tables_register", str(request.remote_addr), str(request.user_agent)))

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sqlite_%';")
        sqlite_tables = cur.fetchall()
        for table in sqlite_tables:
            table_name = table[0]
            cur.execute("INSERT INTO tables_register (name, created_from_ip, created_from_agent, hidden) VALUES (?, ?, ?, ?)", (table_name, str(request.remote_addr), str(request.user_agent), 1))

        conn.commit()
        return jsonify({"result": "success", "data": "Database reset successfully"})
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)})


@app.route("/post/new/table")
def create_table():
    data = {
        "tablename": "",
        "columns": ""
    }

    for column in data:
        if request.args.get(column):
            data[column] = request.args.get(column)
        else:
            return jsonify({"result": "failed", "error": f"{column} value not given"})

    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (data["tablename"],))
        table_exists = cur.fetchone()

        if table_exists:
            return jsonify({"result": "failed", "error": "Table already exists"})

        query = f"CREATE TABLE {data['tablename']} ({data['columns']})"

        cur.execute(query)
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)})
    else:
        try:
            cur.execute("INSERT INTO tables_register (name, created_from_ip, created_from_agent) VALUES (?, ?, ?)", (data["tablename"], str(request.remote_addr), str(request.user_agent)))
            conn.commit()
        except sqlite3.Error as e:
            return jsonify({"result": "failed", "error": str(e)})
        else:
            return jsonify({"result": "success", "data": f"table {data['tablename']} added to database"})

VALID_API_KEY = "abc"


@app.route("/post/new/portfolio-config", methods=['POST'])
def create_portfolio():
    api_key = request.headers.get('x-api-key')
    if api_key != VALID_API_KEY:
        return jsonify({"result": "failed", "error": "Unauthorized"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"result": "failed", "error": "No data provided"}), 400

    required_fields = ["pagename", "title", "bio", "links", "banners", "segments", "icon", "favicon", "colours"]

    for field in required_fields:
        if field not in data:
            return jsonify({"result": "failed", "error": f"{field} value not given"}), 400

    query = "INSERT INTO portfolio (pagename, title, bio, links, banners, segments, icon, favicon, colours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    values = (
        data["pagename"],
        data["title"],
        data["bio"],
        json.dumps(data["links"]),
        json.dumps(data["banners"]),
        json.dumps(data["segments"]),
        data["icon"],
        data["favicon"],
        json.dumps(data["colours"])
    )

    try:
        cur.execute(query, values)
        conn.commit()
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)}), 500
    else:
        return jsonify({"result": "success", "data": "data added to portfolio table"}), 200


@app.route("/get/portfolio-config", methods=['POST'])
def get_portfolio():
    api_key = request.headers.get('x-api-key')
    if api_key != VALID_API_KEY:
        return jsonify({"result": "failed", "error": "Unauthorized"}), 401
    data = {
        "pagename": "",
        "title": "",
        "bio": "",
        "links": {},
        "banners": {},
        "segments": [],
        "icon": "",
        "favicon": "",
        "colours": {}
    }

    # Retrieve 'id' from the request JSON body or headers
    try:
        request_data = request.get_json()
        if request_data is not None:
            id = request_data.get("id")
        else:
            id = request.headers.get("id")
    except Exception as e:
        return str(e)

    try:
        if id:
            if str(id).isdigit():
                id = int(id)
                query = f"SELECT pagename, title, bio, links, banners, segments, icon, favicon, colours FROM portfolio WHERE id = {id}"
            else:
                return jsonify({"result": "failed", "error": "invalid type for id"}), 500
        else:
            query = "SELECT pagename, title, bio, links, banners, segments, icon, favicon, colours FROM portfolio ORDER BY date_added DESC"
    except Exception as e:
        return str(e)

    try:
        cur.execute(query)
        result = cur.fetchone()
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)}), 500  # Changed to 500 to indicate server error
    else:
        if result:
            for key, column in enumerate(data):
                try:
                    data[column] = json.loads(result[key])
                except json.JSONDecodeError:
                    data[column] = result[key]
        else:
            return jsonify({"result": "failed", "error": "No data found"}), 404

    return jsonify({"result": "success", "data": data}), 200


@app.route("/post/new/portfolio-segment", methods=["POST"])
def create_segment():
    api_key = request.headers.get('x-api-key')
    if api_key != VALID_API_KEY:
        return jsonify({"result": "failed", "error": "Unauthorized"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"result": "failed", "error": "No data provided"}), 400

    required_fields = ["name", "title", "text", "images", "icon", "links"]

    for field in required_fields:
        if field not in data:
            return jsonify({"result": "failed", "error": f"{field} value not given"}), 400

    query = "INSERT INTO portfolio_segments (name, title, text, images, icon, links) VALUES (?, ?, ?, ?, ?, ?)"
    values = (
        data["name"],
        data["title"],
        data["text"],
        json.dumps(data["images"]),
        data["icon"],
        json.dumps(data["links"])
    )

    try:
        cur.execute(query, values)
        conn.commit()
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)}), 500
    else:
        return jsonify({"result": "success", "data": "data added to portfolio_segments table"}), 200


@app.route("/get/portfolio-segment", methods=['POST'])
def get_portfolio_segment():
    api_key = request.headers.get('x-api-key')
    if api_key != VALID_API_KEY:
        return jsonify({"result": "failed", "error": "Unauthorized"}), 401
    data = {
        "name": "",
        "title": "",
        "text": "",
        "images": [],
        "icon": "",
        "links": {}
    }

    # Retrieve 'id' from the request JSON body or headers
    try:
        request_data = request.get_json()
        if request_data is not None:
            id = request_data.get("id")
        else:
            id = request.headers.get("id")
    except Exception as e:
        return str(e)

    if id == None:
        return jsonify({"result": "failed", "error": "id not given"}), 500

    try:
        if str(id).isdigit():
            id = int(id)
            query = f"SELECT name, title, text, images, icon, links FROM portfolio_segments WHERE id = {id}"
        else:
            return jsonify({"result": "failed", "error": "invalid type for id"}), 500
    except Exception as e:
        return str(e)

    try:
        cur.execute(query)
        result = cur.fetchone()
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)}), 500  # Changed to 500 to indicate server error
    else:
        if result:
            for key, column in enumerate(data):
                try:
                    data[column] = json.loads(result[key])
                except json.JSONDecodeError:
                    data[column] = result[key]
        else:
            return jsonify({"result": "failed", "error": "No data found"}), 404

    return jsonify({"result": "success", "data": data}), 200


def check_db_backup():
    with open("db_backup/timestamp.txt", "r") as f:
        time_str = f.readline().strip()
    if time_str == "":
        date = datetime.now()
    else:
        date = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    if date.date() != datetime.now().date() or time_str == "":
        with open("db_backup/timestamp.txt", "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        shutil.copy("database.db", "db_backup/database.db")


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000)
