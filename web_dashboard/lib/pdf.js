import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

export function generateReceiptPDF(txn) {
    if (!txn) return;

    // Use 'new' to instantiate jsPDF
    const doc = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
    });

    // --- Header ---
    doc.setFontSize(22);
    doc.setTextColor(37, 99, 235); // Blue color
    doc.text("PHARMAGENT", 105, 20, { align: "center" });

    doc.setFontSize(10);
    doc.setTextColor(100, 116, 139);
    doc.text("Your Trusted Healthcare Partner", 105, 26, { align: "center" });

    // Divider
    doc.setDrawColor(226, 232, 240);
    doc.line(15, 32, 195, 32);

    // --- Transaction Details ---
    doc.setFontSize(12);
    doc.setTextColor(30, 41, 59);
    doc.text(`Receipt ID: ${txn.id || "N/A"}`, 15, 45);
    doc.text(`Date: ${new Date(txn.created_at || Date.now()).toLocaleString("en-IN")}`, 15, 52);

    if (txn.sender) {
        const sender = txn.sender.replace("whatsapp:", "");
        doc.text(`Customer: ${sender === "dashboard" ? "Walk-in" : sender}`, 15, 59);
    }

    // --- Table ---
    const tableColumn = ["Item Name", "Quantity", "Price (₹)", "Amount (₹)"];
    const tableRows = (txn.items || []).map(it => [
        it.name,
        it.quantity,
        (it.mrp || it.unit_price || 0).toFixed(2),
        (it.amount || 0).toFixed(2)
    ]);

    // Use autoTable as a function
    autoTable(doc, {
        startY: 70,
        head: [tableColumn],
        body: tableRows,
        theme: "striped",
        headStyles: { fillColor: [37, 99, 235], textColor: [255, 255, 255] },
        styles: { fontSize: 10, cellPadding: 3 },
        margin: { left: 15, right: 15 },
    });

    // --- Summary ---
    const finalY = doc.lastAutoTable.finalY + 10;
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text(`Grand Total: ₹${(txn.total || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`, 195, finalY, { align: "right" });

    // --- Footer ---
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(148, 163, 184);
    doc.text("Thank you for your visit!", 105, 280, { align: "center" });
    doc.text("PharmAgent · Dedicated to your well-being", 105, 285, { align: "center" });

    // Download the PDF
    doc.save(`Receipt_${txn.id?.slice(0, 8) || "sale"}.pdf`);
}
