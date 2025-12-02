/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { TextAreaPopup } from "@point_of_sale/app/utils/input_popups/textarea_popup"
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();
        this.popup = useService("popup");
    },

    async onClickCustomButton() {
        console.log("yesssss you did it!")
        const order = this.currentOrder;
        const selectedLine = order.get_selected_orderline();

        if (!selectedLine) {
            await this.popup.add(ErrorPopup, {
                title: "No Product Selected",
                body: "Please select a product line first!",
            });
            return;
        }

        // Get current description (you can use description_sale or name)
        const currentDescription = selectedLine.product.description_sale || "";

        // Open popup for editing
        const { confirmed, payload } = await this.popup.add(TextAreaPopup, {
            title: "Edit Product Description",
            startingValue: currentDescription,
        });

        if (confirmed) {
            // Update order line's product description
            selectedLine.product.description_sale = payload;

            // Optional: Show updated text in the order line
            selectedLine.set_full_product_name(payload);

            console.log("Updated description:", payload);

            // 🔁 (Optional) If you want to save it to backend permanently
            // await this.rpc({
            //     model: "product.product",
            //     method: "write",
            //     args: [[selectedLine.product.id], { description_sale: payload }],
            // });
        }
    },
});
