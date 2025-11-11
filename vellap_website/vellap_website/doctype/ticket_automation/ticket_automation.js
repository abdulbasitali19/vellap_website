// Copyright (c) 2025, Abdul Basit and contributors
// For license information, please see license.txt

frappe.ui.form.on('Ticket Automation', {
	refresh: function (frm) {},

	customer: function (frm) {
		if (frm.doc.customer) {
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Quotation',
					filters: { party_name: frm.doc.customer, status: 'draft' },
					fields: ['name', 'grand_total', 'status', 'transaction_date']
				},
				callback: function (r) {
					frm.clear_table('customer_quotations')
					r.message.forEach(q => {
						let row = frm.add_child('customer_quotations')
						row.quotation = q.name
						row.total_amount = q.grand_total
						row.status = q.status
						row.date = q.transaction_date
					})
					frm.refresh_field('customer_quotations')
				}
			})
		}
	},

	validate: function (frm) {
		calculate_total_amount(frm)
	}
})

function calculate_total_amount (frm) {
	let total = 0
	;(frm.doc.customer_quotations || []).forEach(row => {
		total += flt(row.total_amount) // Corrected field
	})
	frm.set_value('total_amount', total)
	frm.refresh_field('total_amount') // Added for guaranteed UI refresh
}
