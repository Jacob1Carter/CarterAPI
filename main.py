from flask import Flask, request, jsonify, render_template, redirect
import sqlite3
from datetime import datetime
import json
import shutil
import hashlib
import random

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
        result = cur.fetchone()

        if result is None:
            hidden = False
        else:
            hidden = result[0] == 1

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
def view_tables():
    error = ""

    if request.method == "POST":
        action, tablename = request.form.get("action").split("-")
        try:
            if action == "delt":
                cur.execute(f"DROP TABLE {tablename}")
                cur.execute(f"DELETE FROM tables_register WHERE name = '{tablename}'")
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
        elif tablename == "keys":
            all_tables.update({tablename: False})
        else:
            all_tables.update({tablename: True})

    return render_template("tables.html", all_tables=all_tables, error=error)


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

                cols_str += f"{col_name} {col_type}{col_not_null}{col_default}{col_pk}{col_other}, "

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

        return redirect("/tables")

    return render_template("new-table.html", error=error)


@app.route("/tables/edit/<tablename>", methods=["GET", "POST"])
def edit_table(tablename):
    if request.method == "POST":
        new_tablename = request.form.get("table-name")
        hidden = 1 if request.form.get("hidden") else 0

        cols_str = ""

        names_replace = {}

        for key in request.form:
            if key.startswith("column-name"):
                column_id = key.split("-")[2]

                col_name = request.form.get(f"column-name-{column_id}")
                col_old_name = request.form.get(f"column-old-name-{column_id}")
                col_type = request.form.get(f"column-type-{column_id}")
                col_not_null = request.form.get(f"column-notnull-{column_id}")
                col_default = request.form.get(f"column-default-{column_id}")
                col_other = request.form.get(f"column-other-{column_id}")
                col_pk = request.form.get(f"column-pk-{column_id}")

                if col_old_name == "":
                    col_old_name = col_name
                else:
                    names_replace.update({col_old_name: col_name})

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

                cols_str += f"{col_old_name} {col_type}{col_not_null}{col_default}{col_pk}{col_other}, "

        if len(cols_str) > 2:
            cols_str = cols_str[:-2]

        # Create the new table
        query = f"CREATE TABLE {new_tablename}_rebuild ({cols_str})"
        try:
            cur.execute(query)
        except sqlite3.Error as e:
            error = f"sqlite3.Error: {str(e)}"

        # Get the column names and types of the new table
        cur.execute(f"PRAGMA table_info({new_tablename}_rebuild)")
        new_columns_info = cur.fetchall()
        new_columns = [info[1] for info in new_columns_info]

        # Get the column names and types of the old table
        cur.execute(f"PRAGMA table_info({tablename})")
        old_columns_info = cur.fetchall()

        # Filter out the columns that exist in the old table and have a compatible data type
        compatible_columns = []
        for old_info in old_columns_info:
            for new_info in new_columns_info:
                if old_info[1] == new_info[1] and old_info[2] == new_info[2]:
                    compatible_columns.append(old_info[1])

        # Construct a SELECT statement that selects only these columns from the old table
        if compatible_columns:
            # Exclude 'id' from the select_columns
            select_columns = ', '.join([col for col in compatible_columns if col != 'id'])

            # Use this SELECT statement in an INSERT INTO ... SELECT statement to insert data into the new table
            insert_statement = f"INSERT INTO {new_tablename}_rebuild ({select_columns}) SELECT {select_columns} FROM {tablename}"
            cur.execute(insert_statement)

        # rename the columns of the new table
        for old_name, new_name in names_replace.items():
            cur.execute(f"ALTER TABLE {new_tablename}_rebuild RENAME COLUMN {old_name} TO {new_name}")

        # rename new table and overwrite old table
        cur.execute(f"DROP TABLE IF EXISTS {tablename}")
        rename_statement = f"ALTER TABLE {new_tablename}_rebuild RENAME TO {new_tablename}"
        cur.execute(rename_statement)

        # update the tables_register table
        cur.execute("UPDATE tables_register SET name = ?, hidden = ? WHERE name = ?", (new_tablename, hidden, tablename))

        conn.commit()
        return redirect(f"/tables/edit/{new_tablename}")

    error = ""

    cur.execute(f"PRAGMA table_info({tablename})")
    columns_info = cur.fetchall()

    unwanted_attributes = {
        # "unwanted_attribute": ["associated attributes"]
        "INTEGER": [],
        "TEXT": [],
        "REAL": [],
        "BLOB": [],
        "TIMESTAMP": [],
        "PRIMARY": ["KEY"],
        "NOT": ["NULL"],
        "DEFAULT": ["CURRENT_TIMESTAMP"],
    }

    # Get the CREATE TABLE statement
    cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tablename}'")
    create_table_statement = cur.fetchone()[0]
    columns = create_table_statement.split("(")[1].split(")")[0].split(",")
    for column in columns:
        pop_list = []
        if column[0] == " ":
            column = column[1:]
        attributes = column.split(" ")
        for key, attribute in enumerate(attributes):
            if attribute in unwanted_attributes:
                for key_2, unwanted in enumerate(unwanted_attributes[attribute]):
                    if unwanted == attributes[key + 1 + key_2]:
                        if key + 1 + key_2 not in pop_list:
                            pop_list.append(key + 1 + key_2)
                pop_list.append(key)
        pop_list.sort(reverse=True)
        for key in pop_list:
            attributes.pop(key)
        if len(attributes) <= 1:
            attributes.append("")
        attributes_str = ""
        for attribute in attributes[1:]:
            attributes_str += f"{attribute} "
        for column_info in columns_info:
            info = list(column_info)
            if info[1] == attributes[0]:
                info.append(attributes_str.strip())
            columns_info[columns_info.index(column_info)] = tuple(info)

    cur.execute(f"SELECT COUNT(*) FROM {tablename}")
    row_count = cur.fetchone()[0]

    hidden = False

    return render_template("edit-table.html", tablename=tablename, columns=columns_info, rowcount=row_count, hidden=hidden, error=error)


@app.route("/table/<tablename>", methods=["GET", "POST"])
def view_table(tablename):
    if tablename == "keys":
        return "Access Denied"
    show = True
    message = ""
    data = ""
    column_names = ""

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [row[0] for row in cur.fetchall()]

    selection = "*"
    table = tablename
    other = "ORDER BY id DESC"

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
def raw_query():
    message = ""
    data = ""

    if request.method == "POST":
        password = request.form.get("password")
        user_query = request.form.get("query")
        if verify_password(password):
            try:
                cur.execute(user_query)
                data = cur.fetchall()
                message = "Query Successful"
            except sqlite3.Error as e:
                message = f"Error: {str(e)}"
        else:
            message = "Incorrect Password, attempt logged"

    return render_template("query.html", message=message, data=data)


@app.route("/post/reset/database")
def reset_database():
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cur.fetchall()

        for table in tables:
            table_name = table[0]
            cur.execute(f"DROP TABLE IF EXISTS {table_name};")

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


@app.route("/keys", methods=["GET", "POST"])
def manage_keys():
    if request.method == "POST":
        if request.form.get("name"):
            name = request.form.get("name")
            valid_key = False
            key = False
            while not valid_key:
                key = generate_key()
                cur.execute("SELECT id FROM keys WHERE key_md5 = ?", (md5_hash(key),))
                if not cur.fetchone():
                    valid_key = True

            if key:
                cur.execute("INSERT INTO keys (name, key_md5) VALUES (?, ?)", (name, md5_hash(key)))
                conn.commit()
                return f"{key}<br><br>Key added to database.<br>Please save this key as it will not be shown again."

        if request.form.get("action"):
            action, name = request.form.get("action").split("-")
            if action == "d":
                cur.execute("DELETE FROM keys WHERE name = ?", (name,))
            if action == "s":
                cur.execute("SELECT suspended FROM keys WHERE name = ?", (name,))
                suspended = cur.fetchone()[0]
                if suspended == 1:
                    cur.execute("UPDATE keys SET suspended = 0 WHERE name = ?", (name,))
                else:
                    cur.execute("UPDATE keys SET suspended = 1 WHERE name = ?", (name,))
            conn.commit()

            cur.execute("SELECT name, suspended FROM keys WHERE id != 1")
            keys = cur.fetchall()

            return render_template("keys.html", keys=keys)
        if verify_password(request.form.get("password")):
            cur.execute("SELECT name, suspended FROM keys WHERE id != 1")
            keys = cur.fetchall()
            return render_template("keys.html", keys=keys)
        else:
            return render_template("keys-auth.html", error="Incorrect Password")
    else:
        return render_template("keys-auth.html", error="")


@app.route("/post/new/portfolio-config", methods=['POST'])
def create_portfolio():
    api_key = request.headers.get('x-api-key')
    if not verify_key(api_key):
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
    if not verify_key(api_key):
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
            row_id = request_data.get("id")
        else:
            row_id = request.headers.get("id")
    except Exception as e:
        return str(e)

    try:
        if row_id:
            if str(row_id).isdigit():
                row_id = int(row_id)
                query = f"SELECT pagename, title, bio, links, banners, segments, icon, favicon, colours FROM portfolio WHERE id = {row_id}"
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
    if not verify_key(api_key):
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
    if not verify_key(api_key):
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
            row_id = request_data.get("id")
        else:
            row_id = request.headers.get("id")
    except Exception as e:
        return str(e)

    if row_id is None:
        return jsonify({"result": "failed", "error": "id not given"}), 500

    try:
        if str(row_id).isdigit():
            row_id = int(row_id)
            query = f"SELECT name, title, text, images, icon, links FROM portfolio_segments WHERE id = {row_id}"
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


@app.route("/get/jiujitsu-user-exists")
def check_jiujitsu_user():
    api_key = request.headers.get('x-api-key')
    if not verify_key(api_key):
        return jsonify({"result": "failed", "error": "Unauthorized"}), 401

    try:
        request_data = request.get_json()
        if request_data is not None:
            username = request_data.get("username")
            email = request_data.get("email")
        else:
            username = request.headers.get("username")
            email = request.headers.get("email")
    except Exception as e:
        return str(e)

    if username is None or email is None:
        return jsonify({"result": "failed", "error": "username and/or email not given"}), 500
    else:
        cur.execute("SELECT username, email FROM SMRJJ_users WHERE username = ? OR email = ?", (username, email))
        result = cur.fetchone()
        if result:
            return jsonify({"result": "success", "data": 1}), 200
        else:
            return jsonify({"result": "success", "data": 0}), 200


@app.route("/post/new-jiujitsu-user")
def create_jiujitsu_user():
    api_key = request.headers.get('x-api-key')
    if not verify_key(api_key):
        return jsonify({"result": "failed", "error": "Unauthorized"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"result": "failed", "error": "No data provided"}), 400

    required_fields = ["username", "password", "email"]

    for field in required_fields:
        if field not in data:
            return jsonify({"result": "failed", "error": f"{field} value not given"}), 400

    query = "INSERT INTO SMRJJ_users (username, password, email) VALUES (?, ?, ?)"
    values = (
        data["username"],
        data["password"],
        data["email"]
    )

    try:
        cur.execute(query, values)
        conn.commit()
    except sqlite3.Error as e:
        return jsonify({"result": "failed", "error": str(e)}), 500
    else:
        return jsonify({"result": "success", "data": "data added to SMRJJ_users table"}), 200


def md5_hash(string):
    return hashlib.md5(string.encode()).hexdigest()


def generate_key():

    choice_alpha = [
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"
    ]

    choices_num = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9
    ]

    string = ""

    for i in range(1, 33):
        if random.random() < 0.4:
            string += random.choice(choice_alpha)
        else:
            string += str(random.choice(choices_num))

    return string


def verify_password(password):
    cur.execute("SELECT key_md5 FROM keys WHERE id = 1")
    password_md5 = cur.fetchone()[0]
    if md5_hash(password) == password_md5:
        log_attempt("admin password", True)
        return True
    else:
        log_attempt("admin password", False)
        return False


def verify_key(key):
    cur.execute("SELECT name FROM keys WHERE key_md5 = ?", (md5_hash(key),))
    name = cur.fetchone()
    if name:
        if name[0] == "admin password":
            log_attempt("unknown", False)
            return False
        else:
            log_attempt(name[0], True)
            return True
    else:
        log_attempt(name[0], False)
        return False


def log_attempt(name, passed):
    ip = request.remote_addr
    if name == "admin password":
        attempt_type = "password"
    else:
        attempt_type = request.url
    detail = f"Passed: {passed}"
    cur.execute("INSERT INTO key_logs (key_name, from_ip, type, detail) VALUES (?, ?, ?, ?)", (name, ip, attempt_type, detail))
    conn.commit()


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
