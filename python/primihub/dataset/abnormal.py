import primihub as ph
import pyarrow
import json
import pandas as pd
from loguru import logger
import mysql.connector
from primihub.dataset import register_dataset


def handle_mixed_column(col):
    col_sum = 0
    col_count = 0
    index_list = []
    for index, val in col.items():
        if val is None:
            logger.info(f"Column {col.name} index {index} has empty value.")
            continue

        try:
            tmp = float(val)
            col_sum = col_sum + tmp
            col_count = col_count + 1
        except:
            index_list.append(index)

    if index_list and col_sum != 0:
        col_avg = col_sum / col_count
        for index in index_list:
            logger.info(
                f"Replace {col[index]} with {col_avg}, column {col.name}, index {index}."
            )
            col[index] = str(col_avg)
    else:
        logger.info(f"Skip column {col.name} due to only missing value in it.")


def handle_abnormal_value_for_csv(path_or_info, col_info):
    df = pd.read_csv(path_or_info)
    df.info(verbose=True)

    logger.info(col_info)

    for col_name, type in col_info.items():
        if type in [1, 2, 3]:
            col = df[col_name]
            if col.dtype == object:
                handle_mixed_column(col)
            df[col_name] = col.astype("int") if type in [1, 3] else col.astype("float")
    df = df.fillna("NA")
    return df


def replace_illegal_string(col_val, col_name, col_type):
    convert_fn = float if col_type == 2 else int
    col_sum = 0
    count = 0
    index = 0
    index_list = []
    new_col_val = []

    for val in col_val:
        if val[0] is None:
            logger.warning(f"Column {col_name} index {index} has empty value null.")
            new_col_val.append("NA")
            index = index + 1
            continue

        if val[0] == "":
            logger.warning(f"Column {col_name} index {index} has empty value ''.")
            new_col_val.append("NA")
            index = index + 1
            continue

        try:
            tmp = convert_fn(val[0])
            col_sum = col_sum + tmp 
            count = count + 1
            new_col_val.append(tmp)
        except Exception as e:
            index_list.append(index)
            new_col_val.append(val[0])
            logger.error(
                f"Can't convert string {val[0]} into number at column {col_name} index {index}, plan to replace it."
            )

        index = index + 1

    if index_list:
        col_avg = col_sum / count if col_type == 2 else col_sum // count
        for index in index_list:
            logger.info(
                f"Replace column {col_name} index {index}'s origin value {new_col_val[index]} to new value {col_avg}."
            )
            new_col_val[index] = col_avg

    return new_col_val

# Now the abnormal value means that a column dtype of which is int or float but 
# has string that can't convert to int or float value. There are four cases when 
# handle abnormal value from database, and missing value in some position in some 
# column is permited, no matter which case.
#
# case 1: a column contain number has type int or long or double, no string will
#         insert into these column, just fill empty position to NA;
#
# case 2: a column contain number but type of them is string, and some string
#         that can't convert into number inserted before, must find out these
#         them then replace them with average value;
#
# case 3: a column contain number has type  of them is string, and all string in
#         this column can converty to number, just fill empty position to NA;
#
# case 4: mix with case 1-3;
#
# Meaning of column dtype number:
#   value 0: string,
#   value 1: integer,
#   value 2: double,
#   value 3: long,
#   value 4: enum,
#   value 5: boolean.


def handle_abnormal_value_for_mysql(path_or_info, col_info):
    db_info = json.loads(path_or_info)

    db_host_port = db_info["dbUrl"]
    db_host, db_port = db_host_port.split(":")

    db_name = db_info["dbName"]
    db_table_name = db_info["dbTableName"]
    db_username = db_info["dbUsername"]
    db_password = db_info["dbPassword"]

    conn = mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_username,
        passwd=db_password,
        database=db_name)

    cursor = conn.cursor()

    sql_str = "desc {}".format(db_table_name)
    try:
        cursor.execute(sql_str)
        table_schema = cursor.fetchall()
    except Exception as e:
        logger.error(e)
        conn.rollback()
        conn.close()
        raise e

    logger.info("Schema of table is {}.".format(table_schema))

    df = pd.DataFrame()
    for column_meta in table_schema:
        col_name = column_meta[0]
        sql_str = "select {} from {}".format(col_name, db_table_name)
        try:
            cursor.execute(sql_str)
            col_val = cursor.fetchall()
        except Exception as e:
            logger.erorr(e)
            conn.rollback()
            conn.close()
            raise e

        new_col = []
        if col_info.get(col_name, None) is not None:
            col_type = col_info[col_name]
            if type(col_val[0][0]) == int or type(col_val[0][0]) == float:
                # Case 1: fill missing value with NA;
                if col_type == 1 or col_type == 3:
                    index = 0
                    for val in col_val:
                        if val[0] is None:
                            new_col.append("NA")
                            logger.info(
                                "Column {} index {} has empty value null.".format(col_name, index))
                        else:
                            new_col.append(int(val[0]))
                        index = index + 1
                elif col_type == 2:
                    index = 0
                    for val in col_val:
                        if val[0] is None:
                            new_col.append("NA")
                            logger.info(
                                "Column {} index {} has empty value null.".format(col_name, index))
                        else:
                            new_col.append(float(val[0]))
                        index = index + 1
            elif type(col_val[0][0]) == str:
                # case 3: fill missing value with NA.
                # case 2: replace abnormal value with average, then do the same
                #         as case 3.
                if col_type == 2 or col_type == 3 or col_type == 1:
                    new_col = replace_illegal_string(
                        col_val, col_name, col_type)

        if len(new_col) == 0:
            for val in col_val:
                new_col.append(val[0])
            df[col_name] = new_col
        else:
            df[col_name] = new_col

    return df


def run_abnormal_process(params_map, dataset_map):
    # Get dataset path or dataset URL.
    dataset_name = params_map["local_dataset"]
    path_or_info = dataset_map[dataset_name]

    use_db = True
    try:
        db_conn_info = json.loads(path_or_info)
        use_db = True
    except Exception as e:
        use_db = False

    # TODO: Remove it, add only for test.
    # use_db = True
    # db_info = {}
    # db_info["dbUrl"] = "192.168.99.21:10036"
    # db_info["dbName"] = "primihub"
    # db_info["dbTableName"] = "test_table"
    # db_info["dbUsername"] = "root"
    # db_info["dbPassword"] = "123456"
    # path_or_info = json.dumps(db_info)
    # filename = "/tmp/output1.csv"

    col_info_str = params_map["ColumnInfo"]
    all_col_info = json.loads(col_info_str)
    col_dtype = all_col_info[dataset_name]["columns"]
    new_dataset_id = all_col_info[dataset_name]["newDataSetId"]

    if use_db is True:
        df = handle_abnormal_value_for_mysql(path_or_info, col_dtype)
    else:
        filename, _ = path_or_info.split(".csv")
        save_path = filename + "_abnormal.csv"
        df = handle_abnormal_value_for_csv(path_or_info, col_dtype)
    
    df.info(verbose=True)
    df.to_csv(save_path, index=False, float_format='%.6f')
    
    dataset_id = all_col_info[dataset_name]["newDataSetId"]
    register_dataset(params_map["DatasetServiceAddr"], "csv", save_path, new_dataset_id)

    logger.info(
        "Finish process abnormal value, result saves to {}.".format(save_path))

# Use below code to start 'run_abnormal_process' in primihub:
#
# import primihub as ph
# from primihub.dataset.abnormal import run_abnormal_process
# 
# @ph.context.function(role="host", protocol="None", datasets=["train_party_0", "train_party_1", "train_party_2"], port="-1")
# def dispatch_abnormal_process():
#         run_abnormal_process(ph.context.Context.params_map,
#                              ph.context.Context.dataset_map)
