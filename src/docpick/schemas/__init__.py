"""Built-in document schemas."""

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.schemas.invoice import InvoiceSchema, InvoiceLineItem
from docpick.schemas.receipt import ReceiptSchema, ReceiptLineItem
from docpick.schemas.bill_of_lading import BillOfLadingSchema, ContainerDetail
from docpick.schemas.purchase_order import PurchaseOrderSchema, POLineItem
from docpick.schemas.certificate import CertificateOfOriginSchema, CertificateItem
from docpick.schemas.bank_statement import BankStatementSchema, Transaction
from docpick.schemas.kr_tax_invoice import KRTaxInvoiceSchema, TaxInvoiceLineItem
from docpick.schemas.id_document import IDDocumentSchema

__all__ = [
    "DocumentSchema",
    "schema_registry",
    # Invoice
    "InvoiceSchema",
    "InvoiceLineItem",
    # Receipt
    "ReceiptSchema",
    "ReceiptLineItem",
    # Bill of Lading
    "BillOfLadingSchema",
    "ContainerDetail",
    # Purchase Order
    "PurchaseOrderSchema",
    "POLineItem",
    # Certificate of Origin
    "CertificateOfOriginSchema",
    "CertificateItem",
    # Bank Statement
    "BankStatementSchema",
    "Transaction",
    # Korean Tax Invoice
    "KRTaxInvoiceSchema",
    "TaxInvoiceLineItem",
    # ID Document
    "IDDocumentSchema",
]
