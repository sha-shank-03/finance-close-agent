"""Read-only QBO v3/minor75 evidence. Inert imports; no model tool or ledger write.

Contract: official Intuit PHP SDK v6.3.1 schema, see docs/u2a-qbo.md.
Only host-pinned ID reads are supported. Query/page/link following is forbidden.
"""

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal

SANDBOX_ORIGIN = "https://sandbox-quickbooks.api.intuit.com"
VERSION = "qbo-u2a-v1"
SCHEMA_VERSION = "intuit-php-v6.3.1-minor75-subset-v1"
MAX_RESPONSE_BYTES = 1024 * 1024
FAILURES = frozenset({"invalid_config", "scope_denied", "schema_error", "incomplete_record",
    "stale_version", "unsupported_currency", "row_bound", "ambiguous_allocation", "unsupported_link",
    "allocation_mismatch", "external_disabled", "cancelled", "deadline", "deadline_uncertain",
    "request_bound", "transport_uncertain", "auth_required", "permission_denied", "record_missing",
    "rate_limited", "server_error", "http_error", "response_rejected", "byte_bound", "date_conflict",
    "overallocated", "snapshot_drift", "repeat_blocked", "owned_cleanup_failed", "credential_forbidden"})


class QboFailure(Exception):
    """Only fixed failure classes escape; never raw body, URL, ID or error text."""
    def __init__(self, kind):
        self.kind = kind if type(kind) is str and kind in FAILURES else "transport_uncertain"
        super().__init__("QBO evidence stopped: " + self.kind)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(data): return hashlib.sha256(data).hexdigest()


def identifier(value, zero=False):
    pattern = r"(?:0|[1-9][0-9]{0,19})" if zero else r"[1-9][0-9]{0,19}"
    if type(value) is not str or not re.fullmatch(pattern, value): raise QboFailure("invalid_config")
    return value


def local_id(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
        raise QboFailure("invalid_config")
    return value


@dataclass(frozen=True)
class BillSelection:
    id: str
    vendor_id: str
    invoice_key: str
    sync_token: str


@dataclass(frozen=True)
class Scope:
    realm_id: str
    bills: tuple
    payments: tuple
    vendor_map: tuple
    as_of_date: str
    max_records: int = 24
    max_requests: int = 50
    max_response_bytes: int = MAX_RESPONSE_BYTES
    max_total_bytes: int = 5 * 1024 * 1024
    deadline_seconds: float = 180.0
    request_seconds: float = 15.0

    @classmethod
    def parse(cls, value):
        fields = {"schema_version", "origin", "api_version", "minor_version", "currency", "realm_id",
                  "bills", "payments", "vendor_map", "as_of_date", "max_records", "max_requests",
                  "max_response_bytes", "max_total_bytes", "deadline_seconds", "request_seconds"}
        try:
            if type(value) is not dict or set(value)-fields or not (fields-{
                "max_records","max_requests","max_response_bytes","max_total_bytes","deadline_seconds","request_seconds"}) <= set(value):
                raise ValueError()
            if type(value["schema_version"]) is not int or value["schema_version"] != 1 or \
                    value["origin"] != SANDBOX_ORIGIN or value["api_version"] != "v3" or \
                    type(value["minor_version"]) is not int or value["minor_version"] != 75 or value["currency"] != "USD":
                raise ValueError()
            realm = identifier(value["realm_id"])
            vendors = value["vendor_map"]
            if type(vendors) is not dict or not 1 <= len(vendors) <= 8: raise ValueError()
            vendor_map = tuple(sorted((identifier(k),local_id(v)) for k,v in vendors.items()))
            if len({v for k,v in vendor_map}) != len(vendor_map): raise ValueError()
            bills, payments = value["bills"], value["payments"]
            if type(bills) is not dict or not 1 <= len(bills) <= 8 or type(payments) is not dict or len(payments)>16:
                raise ValueError()
            selected=[]
            for key, entry in sorted(bills.items()):
                if type(entry) is not dict or set(entry) != {"vendor_id","invoice_key","sync_token"}: raise ValueError()
                vendor = identifier(entry["vendor_id"])
                parts = entry["invoice_key"].split(":")
                if vendor not in vendors or len(parts)!=2 or local_id(parts[0]) != vendors[vendor]: raise ValueError()
                local_id(parts[1])
                selected.append(BillSelection(identifier(key),vendor,entry["invoice_key"],identifier(entry["sync_token"],True)))
            if len({b.invoice_key for b in selected}) != len(selected): raise ValueError()
            paid = tuple(sorted((identifier(k),identifier(v,True)) for k,v in payments.items()))
            cutoff = value["as_of_date"]
            if type(cutoff) is not str or date.fromisoformat(cutoff).isoformat() != cutoff: raise ValueError()
            bounds={}
            for key, maximum, minimum, default in [
                ("max_records",24,1,24),("max_requests",50,1,50),
                ("max_response_bytes",MAX_RESPONSE_BYTES,256,MAX_RESPONSE_BYTES),
                ("max_total_bytes",5*1024*1024,256,5*1024*1024)]:
                item=value.get(key,default)
                if type(item) is not int or not minimum<=item<=maximum: raise ValueError()
                bounds[key]=item
            for key,maximum,minimum,default in [("deadline_seconds",180,.5,180), ("request_seconds",15,.05,15)]:
                item=value.get(key,default)
                if type(item) not in {float,int} or not minimum<=item<=maximum: raise ValueError()
                bounds[key]=float(item)
            if len(selected)+len(paid)>bounds["max_records"] or bounds["max_response_bytes"]>bounds["max_total_bytes"]:
                raise ValueError()
            return cls(realm,tuple(selected),paid,vendor_map,cutoff,**bounds)
        except (ValueError,TypeError,KeyError,AttributeError): raise QboFailure("invalid_config") from None

    @property
    def hash(self): return digest(canonical(asdict(self)).encode())


@dataclass(frozen=True)
class ReadRequest:
    realm_id: str
    entity: str
    id: str
    scope_hash: str

    @property
    def path(self):
        return f"/v3/company/{self.realm_id}/{self.entity.lower()}/{self.id}?minorversion=75"

    def validate(self, scope):
        approved = {b.id for b in scope.bills} if self.entity == "Bill" else dict(scope.payments) if self.entity == "BillPayment" else set()
        if self.realm_id != scope.realm_id or self.id not in approved or self.scope_hash != scope.hash:
            raise QboFailure("scope_denied")


def parse_json(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result: raise ValueError()
            result[key]=value
        return result
    try:
        return json.loads(raw.decode("utf-8"),object_pairs_hook=pairs,parse_float=Decimal,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError,RecursionError): raise QboFailure("schema_error") from None


def money(value):
    if type(value) not in {int,Decimal}: raise QboFailure("schema_error")
    value=Decimal(value)
    if not value.is_finite() or value.as_tuple().exponent < -2 or not 0<=value<=Decimal("999999999.99"):
        raise QboFailure("schema_error")
    return int(value*100)


def timestamp(value):
    try:
        if type(value) is not str or len(value)>40 or datetime.fromisoformat(value).tzinfo is None: raise ValueError()
        return value
    except ValueError: raise QboFailure("schema_error") from None


def entity_hash(entity):
    # Private-text changes also fail consistency; no private text is exported.
    # Tag every node to preserve number/string/object types. Decimal str avoids
    # expanding a hostile unknown-field exponent into a huge fixed-point value.
    def tagged(value):
        if type(value) is dict: return ["object",[[k,tagged(v)] for k,v in sorted(value.items())]]
        if type(value) is list: return ["array",[tagged(v) for v in value]]
        if type(value) is Decimal: return ["decimal",str(value)]
        if type(value) is int: return ["integer",str(value)]
        if type(value) is str: return ["string",value]
        if type(value) is bool: return ["boolean",value]
        if value is None: return ["null"]
        raise QboFailure("schema_error")
    return digest(canonical(tagged(entity)).encode())


def normalize(entity, kind, key, scope):
    try:
        versions={b.id:b.sync_token for b in scope.bills} if kind=="Bill" else dict(scope.payments)
        if type(entity) is not dict or entity.get("Id") != key or entity.get("domain") != "QBO" or \
                entity.get("sparse") is not False or "status" in entity:
            raise QboFailure("incomplete_record")
        version=entity["SyncToken"]
        if type(version) is not str or not re.fullmatch(r"(?:0|[1-9][0-9]{0,19})",version): raise QboFailure("schema_error")
        if version != versions[key]: raise QboFailure("stale_version")
        vendor=entity["VendorRef"]["value"]
        if type(vendor) is not str or vendor not in dict(scope.vendor_map): raise QboFailure("scope_denied")
        if entity["CurrencyRef"]["value"] != "USD": raise QboFailure("unsupported_currency")
        if "ExchangeRate" in entity and (type(entity["ExchangeRate"]) not in {int,Decimal} or entity["ExchangeRate"]!=1):
            raise QboFailure("unsupported_currency")
        txn_date=entity["TxnDate"]
        if type(txn_date) is not str or date.fromisoformat(txn_date).isoformat()!=txn_date or txn_date>scope.as_of_date:
            raise QboFailure("schema_error")
        updated=timestamp(entity["MetaData"]["LastUpdatedTime"])
        total=money(entity["TotalAmt"])
        if total<=0: raise QboFailure("incomplete_record")
        facts={"entity":kind,"id":key,"sync_token":version,"vendor_id":vendor,
               "local_vendor_id":dict(scope.vendor_map)[vendor],"currency":"USD","txn_date":txn_date,
               "total_cents":total,"last_updated_time":updated}
        paths={"id":"Id","sync_token":"SyncToken","vendor_id":"VendorRef.value",
               "currency":"CurrencyRef.value","txn_date":"TxnDate","total_cents":"TotalAmt",
               "last_updated_time":"MetaData.LastUpdatedTime"}
        if kind=="Bill":
            selected=next(b for b in scope.bills if b.id==key)
            if vendor!=selected.vendor_id: raise QboFailure("scope_denied")
            balance=money(entity["Balance"])
            if balance>total: raise QboFailure("schema_error")
            facts.update(balance_cents=balance,invoice_key=selected.invoice_key)
            paths["balance_cents"]="Balance"
        else:
            if entity.get("PayType") not in {"Check","CreditCard"}: raise QboFailure("schema_error")
            lines=entity["Line"]
            if type(lines) is not list or not 1<=len(lines)<=8: raise QboFailure("row_bound")
            allocations=[];seen=set();bills={b.id:b for b in scope.bills}
            for index,line in enumerate(lines):
                links=line["LinkedTxn"]
                if type(links) is not list or len(links)!=1: raise QboFailure("ambiguous_allocation")
                link=links[0]
                if type(link) is not dict or set(link)!={"TxnId","TxnType"} or link["TxnType"]!="Bill":
                    raise QboFailure("unsupported_link")
                bill_id=link["TxnId"]
                if type(bill_id) is not str or bill_id not in bills or bills[bill_id].vendor_id!=vendor:
                    raise QboFailure("scope_denied")
                if bill_id in seen: raise QboFailure("ambiguous_allocation")
                seen.add(bill_id);amount=money(line["Amount"])
                if amount<=0: raise QboFailure("incomplete_record")
                allocations.append({"bill_id":bill_id,"amount_cents":amount})
                paths[f"allocations[{index}].bill_id"]=f"Line[{index}].LinkedTxn[0].TxnId"
                paths[f"allocations[{index}].amount_cents"]=f"Line[{index}].Amount"
            if sum(a["amount_cents"] for a in allocations)!=total: raise QboFailure("allocation_mismatch")
            facts["allocations"]=allocations
        return facts,paths
    except (KeyError,TypeError,ValueError,AttributeError): raise QboFailure("schema_error") from None


@dataclass(frozen=True)
class Capture:
    document: str
    events: str

    def as_dict(self): return json.loads(self.document)


class QboAdapter:
    """A single-use capture. Requests/IDs/mapping are never model-selected."""
    def __init__(self, config, *, transport, mode="contract-double", clock=time.monotonic,
                 wait=None, cancelled=None):
        self.scope=Scope.parse(config)
        if mode not in {"contract-double","local-http-double","external-sandbox"}: raise QboFailure("invalid_config")
        if mode!="contract-double":
            from .qbo_transport import OwnedQboTransport
            if type(transport) is not OwnedQboTransport or transport.mode!=mode or transport.scope!=self.scope:
                raise QboFailure("scope_denied")
        if mode=="external-sandbox" and not getattr(transport,"external_authorized",False): raise QboFailure("external_disabled")
        self.transport,self.mode,self.clock,self.cancelled=transport,mode,clock,cancelled
        self.wait=wait or self._wait
        self.state="READY";self.events=[];self.requests=0;self.total_bytes=0;self.started=None;self.last_start=None

    def _remaining(self):
        if self.cancelled and self.cancelled(): raise QboFailure("cancelled")
        remaining=self.scope.deadline_seconds-(self.clock()-self.started)
        if remaining<=0: raise QboFailure("deadline")
        return remaining

    def _wait(self,seconds):
        end=self.clock()+seconds
        while self.clock()<end:
            self._remaining();time.sleep(min(.05,end-self.clock()))

    def _read(self,kind,key):
        remaining=self._remaining()
        if self.requests>=self.scope.max_requests: raise QboFailure("request_bound")
        if self.last_start is not None:
            spacing=max(0,.5-(self.clock()-self.last_start))
            if spacing>=remaining: raise QboFailure("deadline")
            self.wait(spacing)
        remaining=self._remaining();request=ReadRequest(self.scope.realm_id,kind,key,self.scope.hash)
        request.validate(self.scope);self.requests+=1;self.last_start=self.clock()
        event={"sequence":self.requests,"mode":self.mode,"method":"GET","entity":kind,
               "record_hash":digest((kind+":"+key).encode()),"scope_hash":self.scope.hash,
               "status":"started","http_status":None,"response_bytes":None,"response_sha256":None,
               "automatic_http_retries":0,"model_calls":0,"cleanup_complete":None}
        self.events.append(event);before=self.clock()
        try:
            timeout=min(self.scope.request_seconds,remaining)
            response=self.transport(request,timeout,self.cancelled)
            self._remaining()
            if self.clock()-before>timeout: raise QboFailure("deadline_uncertain")
            if type(response) is not dict or type(response.get("status")) is not int or \
                    type(response.get("body")) is not bytes or response.get("cleanup_complete") is not True:
                raise QboFailure("transport_uncertain")
            event.update(http_status=response["status"],cleanup_complete=True,response_bytes=len(response["body"]))
            status=response["status"]
            if status!=200:
                statuses={401:"auth_required",403:"permission_denied",404:"record_missing",429:"rate_limited"}
                raise QboFailure(statuses.get(status,"server_error" if 500<=status<=599 else "http_error"))
            if response.get("kind")!="ok": raise QboFailure("response_rejected")
            raw=response["body"]
            self.total_bytes+=len(raw)
            if len(raw)>self.scope.max_response_bytes or self.total_bytes>self.scope.max_total_bytes: raise QboFailure("byte_bound")
            event["response_sha256"]=digest(raw)
            value=parse_json(raw)
            if type(value) is not dict or "Fault" in value or set(value)!={kind,"time"}: raise QboFailure("schema_error")
            server_time=timestamp(value["time"])
            facts,paths=normalize(value[kind],kind,key,self.scope)
            facts.update(response_sha256=digest(raw),entity_sha256=entity_hash(value[kind]),server_time=server_time,
                         field_provenance=[{"field":field,"json_path":"$."+kind+"."+path,"response_sha256":digest(raw)} for field,path in sorted(paths.items())])
            self._remaining();event["status"]="read_validated"
            return facts
        except KeyboardInterrupt: event["status"]="cancelled";raise QboFailure("cancelled") from None
        except QboFailure as exc:
            event["status"]=exc.kind
            if hasattr(exc,"cleanup_complete"): event["cleanup_complete"]=exc.cleanup_complete
            raise
        except Exception: event["status"]="transport_uncertain";raise QboFailure("transport_uncertain") from None
        finally: event["elapsed_seconds"]=max(0,self.clock()-before)

    def capture(self):
        if self.state!="READY": raise QboFailure("repeat_blocked")
        self.state="STARTED"
        try:
            self.started=self.clock()
            bills=[self._read("Bill",b.id) for b in self.scope.bills]
            payments=[self._read("BillPayment",key) for key,version in self.scope.payments]
            by_id={b["id"]:b for b in bills};paid={b["id"]:0 for b in bills}
            for payment in payments:
                for allocation in payment["allocations"]:
                    bill=by_id[allocation["bill_id"]]
                    if payment["txn_date"]<bill["txn_date"]: raise QboFailure("date_conflict")
                    paid[bill["id"]]+=allocation["amount_cents"]
            if any(paid[b["id"]]>b["total_cents"] for b in bills): raise QboFailure("overallocated")
            # Re-read the same pinned IDs. Wrapper response 'time' may advance;
            # the entity hash/SyncToken must remain identical. No links are read.
            for previous in bills+payments:
                current=self._read(previous["entity"],previous["id"])
                if current["entity_sha256"]!=previous["entity_sha256"]: raise QboFailure("snapshot_drift")
            self._remaining()
            summaries=[{"bill_id":b["id"],"selected_payment_cents":paid[b["id"]],
                        "remaining_if_selected_only_cents":b["total_cents"]-paid[b["id"]],
                        "snapshot_balance_cents":b["balance_cents"],
                        "selected_scope_agrees_with_balance":b["total_cents"]-paid[b["id"]]==b["balance_cents"]} for b in bills]
            document={"schema_version":1,"adapter_version":VERSION,"api_version":"v3","minor_version":75,
                      "schema_contract":SCHEMA_VERSION,"evidence_mode":self.mode,"scope_hash":self.scope.hash,
                      "bills":bills,"bill_payments":payments,"partial_payment_summary":summaries,
                      "selected_records_complete":True,"ap_history_complete":False,"ledger_imported":False,
                      "posting_supported":False,"hold":"EXTERNAL_HISTORY_NOT_CERTIFIED",
                      "requests":self.requests,"query_pages":0,"rows_per_response":1,
                      "response_bytes":self.total_bytes,"active_seconds":self.clock()-self.started,
                      "automatic_http_retries":0,"automatic_inference_retries":0,"model_calls":0,
                      "snapshot_claim":"Consistent re-reads of selected IDs, not an atomic company snapshot or complete AP ledger."}
            self.state="CAPTURED"
            return Capture(canonical(document),"".join(canonical(e)+"\n" for e in self.events))
        except QboFailure as exc:
            self.state="HALTED"
            raise exc from None
        except KeyboardInterrupt:
            self.state="HALTED"
            raise QboFailure("cancelled") from None
        except BaseException:
            self.state="HALTED"
            raise QboFailure("transport_uncertain") from None
