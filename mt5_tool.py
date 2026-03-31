__version__ = "0.5.9"

import MetaTrader5 as mt5
import json
import argparse
import os
import glob
import threading
import socketserver
import http.server
import urllib.parse
import time
from datetime import datetime, timedelta


# ─── Stato globale daemon ───────────────────────────────────────────────────
_daemon_lock = threading.Lock()
_current_terminal_path = None   # path exe del terminale attualmente connesso


def _ensure_terminal(terminal_path):
    """Assicura che MT5 sia connesso al terminale richiesto.
    Se è già connesso a quello stesso terminale e la connessione è viva, non fa nulla.
    Altrimenti esegue shutdown + initialize verso il nuovo terminale.
    DEVE essere chiamato con _daemon_lock già acquisito.
    """
    global _current_terminal_path
    if _current_terminal_path == terminal_path:
        if mt5.terminal_info() is not None:
            return  # già connesso e vivo
    # Serve (ri)inizializzare
    if _current_terminal_path is not None:
        mt5.shutdown()
        _current_terminal_path = None
    ok = mt5.initialize(path=terminal_path)
    if not ok:
        raise ConnectionError("MT5 initialize fallito: " + str(mt5.last_error()))
    _current_terminal_path = terminal_path


# ─── Helpers di connessione (usati dalla CLI) ───────────────────────────────

def discover_terminals():
    import psutil
    found = {}
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if 'terminal64' in proc.info['name'].lower():
                path = proc.info['exe']
                folder = path.replace('\\terminal64.exe', '')
                name = folder.split('\\')[-1].lower()
                name = name.replace(' ', '_').replace('metatrader', 'mt5').replace('meta_trader', 'mt5')
                found[name] = path
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return found


def connect(terminal_path):
    ok = mt5.initialize(path=terminal_path)
    if not ok:
        raise ConnectionError("MT5 initialize fallito: " + str(mt5.last_error()))


def disconnect():
    mt5.shutdown()


# ─── Funzioni di lettura MT5 ────────────────────────────────────────────────

def get_open_positions(terminal_path, already_connected=False):
    if not already_connected:
        connect(terminal_path)
    positions = mt5.positions_get()
    result = []
    if positions:
        for p in positions:
            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                "volume": p.volume,
                "open_price": p.price_open,
                "current_price": p.price_current,
                "sl": p.sl if p.sl > 0 else None,
                "tp": p.tp if p.tp > 0 else None,
                "profit": p.profit,
                "swap": p.swap,
                "open_time": datetime.fromtimestamp(p.time).isoformat(),
                "comment": p.comment,
                "magic": p.magic
            })
    if not already_connected:
        disconnect()
    return result


def get_account_info(terminal_path, already_connected=False):
    if not already_connected:
        connect(terminal_path)
    acc = mt5.account_info()
    if not acc:
        if not already_connected:
            disconnect()
        return {"error": "impossibile leggere info conto"}
    result = {
        "login":        acc.login,
        "name":         acc.name,
        "server":       acc.server,
        "broker":       acc.company,
        "currency":     acc.currency,
        "leverage":     acc.leverage,
        "balance":      round(acc.balance, 2),
        "equity":       round(acc.equity, 2),
        "margin":       round(acc.margin, 2),
        "margin_free":  round(acc.margin_free, 2),
        "margin_level": round(acc.margin_level, 2) if acc.margin_level else None,
        "profit":       round(acc.profit, 2),
    }
    if not already_connected:
        disconnect()
    return result


def get_trade_history(terminal_path, days=30, already_connected=False):
    if not already_connected:
        connect(terminal_path)
    date_from = datetime.now() - timedelta(days=days)
    date_to = datetime.now()

    orders = mt5.history_orders_get(date_from, date_to)
    deals = mt5.history_deals_get(date_from, date_to)

    if not already_connected:
        disconnect()

    if not orders or not deals:
        return []

    deals_by_order = {}
    for d in deals:
        if d.order not in deals_by_order:
            deals_by_order[d.order] = []
        deals_by_order[d.order].append(d)

    result = []
    processed_positions = {}

    for d in sorted(deals, key=lambda x: x.time):
        if d.type not in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL):
            continue

        pos_id = d.position_id

        if d.entry == mt5.DEAL_ENTRY_IN:
            processed_positions[pos_id] = {
                "position_id": pos_id,
                "symbol": d.symbol,
                "type": "buy" if d.type == mt5.DEAL_TYPE_BUY else "sell",
                "volume": d.volume,
                "open_price": d.price,
                "open_time": datetime.fromtimestamp(d.time).isoformat(),
                "close_price": None,
                "close_time": None,
                "profit": 0.0,
                "swap": 0.0,
                "commission": d.commission,
                "magic": d.magic,
                "comment": d.comment
            }

        elif d.entry == mt5.DEAL_ENTRY_OUT and pos_id in processed_positions:
            trade = processed_positions[pos_id]
            trade["close_price"] = d.price
            trade["close_time"] = datetime.fromtimestamp(d.time).isoformat()
            trade["profit"] = round(d.profit, 2)
            trade["swap"] = round(d.swap, 2)
            trade["commission"] = round(trade["commission"] + d.commission, 2)
            trade["net_profit"] = round(d.profit + d.swap + trade["commission"], 2)
            result.append(trade)
            del processed_positions[pos_id]

    result.sort(key=lambda x: x["open_time"], reverse=True)
    return result


def get_expert_log(terminal_path, lines=100, already_connected=False):
    if not already_connected:
        connect(terminal_path)
    info = mt5.terminal_info()
    if not already_connected:
        disconnect()

    if not info:
        return {"error": "impossibile leggere info terminale"}

    terminal_data_path = info.data_path
    log_pattern = os.path.join(terminal_data_path, "logs", "*.log")
    log_files = glob.glob(log_pattern)

    if not log_files:
        return {"error": "nessun file log trovato", "path_cercato": log_pattern}

    latest_log = max(log_files, key=os.path.getmtime)

    try:
        with open(latest_log, 'r', encoding='utf-16', errors='replace') as f:
            all_lines = f.readlines()
    except Exception:
        try:
            with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
        except Exception as e:
            return {"error": "impossibile leggere il log: " + str(e)}

    expert_lines = [l.strip() for l in all_lines if l.strip()]
    last_lines = expert_lines[-lines:] if len(expert_lines) > lines else expert_lines

    return {
        "log_file": latest_log,
        "total_lines": len(expert_lines),
        "showing_last": len(last_lines),
        "entries": last_lines
    }


def get_symbols(terminal_path, already_connected=False):
    if not already_connected:
        connect(terminal_path)
    symbols = mt5.symbols_get()
    result = []
    if symbols:
        for s in symbols:
            result.append({
                "name": s.name,
                "description": s.description,
                "currency_base": s.currency_base,
                "currency_profit": s.currency_profit,
                "digits": s.digits,
                "spread": s.spread,
                "visible": s.visible
            })
    if not already_connected:
        disconnect()
    return result


def get_symbol_info(terminal_path, symbol, already_connected=False):
    if not already_connected:
        connect(terminal_path)
    mt5.symbol_select(symbol, True)
    s = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if not s:
        if not already_connected:
            disconnect()
        return {"error": "simbolo non trovato: " + symbol}

    result = {
        "name": s.name,
        "description": s.description,
        "currency_base": s.currency_base,
        "currency_profit": s.currency_profit,
        "currency_margin": s.currency_margin,
        "digits": s.digits,
        "spread": s.spread,
        "spread_float": s.spread_float,
        "contract_size": s.trade_contract_size,
        "volume_min": s.volume_min,
        "volume_max": s.volume_max,
        "volume_step": s.volume_step,
        "trade_mode": s.trade_mode,
        "swap_long": s.swap_long,
        "swap_short": s.swap_short,
        "margin_initial": s.margin_initial,
        "bid": tick.bid if tick else None,
        "ask": tick.ask if tick else None,
        "last_tick": datetime.fromtimestamp(tick.time).isoformat() if tick else None
    }
    if not already_connected:
        disconnect()
    return result


# ─── Daemon HTTP ─────────────────────────────────────────────────────────────

_daemon_terminal_paths: dict = {}  # nome → path exe (popolato da run_daemon)


class _DaemonHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        def p(key, default=None):
            vals = params.get(key)
            return urllib.parse.unquote(vals[0]) if vals else default

        function = p("function")
        terminal = p("terminal")
        days     = int(p("days", 30))
        lines_n  = int(p("lines", 100))
        symbol   = p("symbol")

        if not function:
            self._respond({"error": "parametro function mancante"})
            return

        terminal_path = None
        if terminal:
            terminal_path = _daemon_terminal_paths.get(terminal)
            if not terminal_path:
                _daemon_terminal_paths.update(discover_terminals())
                terminal_path = _daemon_terminal_paths.get(terminal)
            if not terminal_path:
                self._respond({
                    "error": "terminal non trovato",
                    "available": list(_daemon_terminal_paths.keys())
                })
                return

        try:
            with _daemon_lock:
                if terminal_path:
                    _ensure_terminal(terminal_path)

                if function == "list_terminals":
                    result = {}
                    terminals = discover_terminals()
                    _daemon_terminal_paths.update(terminals)
                    for name, path in terminals.items():
                        try:
                            _ensure_terminal(path)
                            acc = mt5.account_info()
                            info = mt5.terminal_info()
                            result[name] = {
                                "path": path,
                                "login": acc.login if acc else None,
                                "name": acc.name if acc else None,
                                "server": acc.server if acc else None,
                                "broker": acc.company if acc else None,
                                "connected": info.connected if info else False
                            }
                        except Exception as e:
                            result[name] = {"path": path, "error": str(e)}
                elif function == "get_open_positions":
                    result = get_open_positions(terminal_path, already_connected=True)
                elif function == "get_account_info":
                    result = get_account_info(terminal_path, already_connected=True)
                elif function == "get_trade_history":
                    result = get_trade_history(terminal_path, days=days, already_connected=True)
                elif function == "get_expert_log":
                    result = get_expert_log(terminal_path, lines=lines_n, already_connected=True)
                elif function == "get_symbols":
                    result = get_symbols(terminal_path, already_connected=True)
                elif function == "get_symbol_info":
                    if not symbol:
                        result = {"error": "parametro symbol mancante"}
                    else:
                        result = get_symbol_info(terminal_path, symbol, already_connected=True)
                elif function == "get_all_positions":
                    result = {}
                    all_terminals = discover_terminals()
                    _daemon_terminal_paths.update(all_terminals)
                    for t_name, t_path in all_terminals.items():
                        try:
                            _ensure_terminal(t_path)
                            positions = get_open_positions(t_path, already_connected=True)
                            acc = mt5.account_info()
                            result[t_name] = {
                                "positions": positions,
                                "account": {
                                    "balance": round(acc.balance, 2),
                                    "equity": round(acc.equity, 2),
                                    "profit": round(acc.profit, 2),
                                } if acc else None,
                            }
                        except Exception as e:
                            result[t_name] = {"error": str(e)}
                else:
                    result = {"error": "funzione non riconosciuta"}

            self._respond(result)
        except Exception as e:
            self._respond({"error": str(e)})

    def _respond(self, data):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silenzia log HTTP su stdout


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def run_daemon():
    global _daemon_terminal_paths
    _daemon_terminal_paths = discover_terminals()
    server = _ThreadingHTTPServer(("127.0.0.1", 9999), _DaemonHandler)
    server.serve_forever()


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--function", default=None)
    parser.add_argument("--terminal", default=None)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--lines", type=int, default=100)
    parser.add_argument("--symbol", default=None)
    args = parser.parse_args()

    if args.daemon:
        run_daemon()
        sys.exit(0)

    if not args.function:
        print(json.dumps({"error": "specifica --function o --daemon"}))
        sys.exit(1)

    terminals = discover_terminals()

    if args.function == "list_terminals":
        result = {}
        for name, path in terminals.items():
            try:
                connect(path)
                acc = mt5.account_info()
                info = mt5.terminal_info()
                result[name] = {
                    "path": path,
                    "login": acc.login if acc else None,
                    "name": acc.name if acc else None,
                    "server": acc.server if acc else None,
                    "broker": acc.company if acc else None,
                    "connected": info.connected if info else False
                }
                disconnect()
            except Exception as e:
                result[name] = {"path": path, "error": str(e)}
        print(json.dumps(result, indent=2))

    else:
        if not args.terminal:
            print(json.dumps({"error": "specifica --terminal"}))
        elif args.terminal not in terminals:
            print(json.dumps({"error": "terminal non trovato", "available": list(terminals.keys())}))
        else:
            path = terminals[args.terminal]
            try:
                if args.function == "get_account_info":
                    print(json.dumps(get_account_info(path), indent=2))
                elif args.function == "get_open_positions":
                    print(json.dumps(get_open_positions(path), indent=2))
                elif args.function == "get_trade_history":
                    print(json.dumps(get_trade_history(path, args.days), indent=2))
                elif args.function == "get_expert_log":
                    print(json.dumps(get_expert_log(path, args.lines), indent=2))
                elif args.function == "get_symbols":
                    print(json.dumps(get_symbols(path), indent=2))
                elif args.function == "get_symbol_info":
                    if not args.symbol:
                        print(json.dumps({"error": "specifica --symbol"}))
                    else:
                        print(json.dumps(get_symbol_info(path, args.symbol), indent=2))
                else:
                    print(json.dumps({"error": "funzione non riconosciuta"}))
            except Exception as e:
                print(json.dumps({"error": str(e)}))
