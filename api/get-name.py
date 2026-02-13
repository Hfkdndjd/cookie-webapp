import json
import os
import psycopg2

def handler(request):
    """Vercel Serverless Function — возвращает имя тейкера после оплаты."""
    
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": ""
        }

    params = request.args if hasattr(request, 'args') else {}
    completion_id = params.get('completion_id')
    user_id = params.get('user_id')

    if not completion_id:
        return response({"error": "missing completion_id"}, 400)

    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', 5432)),
            dbname=os.environ.get('DB_NAME', 'cookie_bot'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASS', ''),
        )
        cur = conn.cursor()

        # Проверяем что оплата прошла
        cur.execute(
            "SELECT taker_name, score, paid FROM completions WHERE id = %s",
            (int(completion_id),)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return response({"error": "not found"}, 404)

        taker_name, score, paid = row

        if not paid:
            return response({"error": "not paid"}, 403)

        return response({"name": taker_name, "score": score})

    except Exception as e:
        return response({"error": str(e)}, 500)


def response(data: dict, status: int = 200):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(data)
    }
