/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { menuService } from "@web/webclient/menus/menu_service";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";

/**
 * Company-wise menu visibility.
 *
 * We deliberately do this filtering on the CLIENT side instead of trying to
 * make the server-side `load_menus` company-aware: that route is a plain
 * (non-JSON-RPC) HTTP GET call, cached with @tools.ormcache on Odoo's side,
 * and the "currently selected company" (the `cids` cookie) is not reliably
 * translated into `env.company` for that specific route. The browser
 * however always knows exactly which company is currently active
 * (`user.activeCompanies`), so filtering here is simple and 100% reliable.
 */
patch(menuService, {
    async start(env) {
        const result = await super.start(env);

        let restrictions = {};
        try {
            restrictions = await rpc("/company_wise_menu/get_restrictions");
        } catch (error) {
            console.error("company_wise_menu: could not fetch restrictions", error);
            return result;
        }

        if (!restrictions || !Object.keys(restrictions).length) {
            return result;
        }

        const isAllowed = (menuId) => {
            const allowedCompanyIds = restrictions[String(menuId)];
            if (!allowedCompanyIds) {
                // no restriction set on this menu -> always visible
                return true;
            }
            const currentCompanyId = user.activeCompanies[0]?.id;
            return allowedCompanyIds.includes(currentCompanyId);
        };

        const originalGetApps = result.getApps.bind(result);
        result.getApps = function () {
            return originalGetApps().filter((app) => isAllowed(app.id));
        };

        const originalGetMenuAsTree = result.getMenuAsTree.bind(result);
        result.getMenuAsTree = function (menuID) {
            const tree = originalGetMenuAsTree(menuID);
            if (tree && tree.childrenTree) {
                tree.childrenTree = tree.childrenTree.filter((child) => isAllowed(child.id));
            }
            return tree;
        };

        return result;
    },
});
