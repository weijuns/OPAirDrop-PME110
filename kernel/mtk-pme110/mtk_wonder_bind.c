// SPDX-License-Identifier: GPL-2.0-only
/*
 * PME110 research module: bind the existing MTK Wonder component and stock
 * wonder.ko without replacing WLAN or persisting a device-tree overlay.
 *
 * Inspired by AirDropVivoCN's GPL wonder_shim, but the provider here is the
 * existing MTK vendor_wonder_dev driver, not a replacement CNSS component.
 * Default mode validates donors only. Activation must be requested explicitly.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/slab.h>

static_assert(sizeof(struct module) == 0x640);
static_assert(sizeof(struct platform_device) == 0x3f0);
static_assert(offsetof(struct platform_device, dev) == 0x10);
static_assert(sizeof(struct device) == 0x390);
static_assert(offsetof(struct device, driver_data) == 0x98);
static_assert(offsetof(struct device, of_node) == 0x2e8);
static_assert(sizeof(struct device_node) == 0xf8);
static_assert(sizeof(struct property) == 0x68);

static char *provider_node;
static char *wonder_node;
static bool activate;
module_param(provider_node, charp, 0444);
module_param(wonder_node, charp, 0444);
module_param(activate, bool, 0444);
MODULE_PARM_DESC(provider_node, "Existing unused leaf DT node with a phandle");
MODULE_PARM_DESC(wonder_node, "Different existing unused leaf DT node");
MODULE_PARM_DESC(activate, "Create devices after validation (default: false)");

static struct device_node *provider_np, *wonder_np;
static struct platform_device *provider_pdev, *wonder_pdev;
static struct property *link_prop;

/* Keep the properties in heap memory: OF retains removed properties in its
 * deadprops list. They must never point into unloadable module storage.
 */
static struct property *alloc_link(u32 phandle)
{
	struct property *prop;
	__be32 *value;

	prop = kzalloc(sizeof(*prop), GFP_KERNEL);
	if (!prop)
		return NULL;
	prop->name = kstrdup("wondertap-provider", GFP_KERNEL);
	value = kmalloc(sizeof(*value), GFP_KERNEL);
	if (!prop->name || !value) {
		kfree(prop->name);
		kfree(value);
		kfree(prop);
		return NULL;
	}
	*value = cpu_to_be32(phandle);
	prop->value = value;
	prop->length = sizeof(*value);
	return prop;
}

static void free_unpublished_link(struct property *prop)
{
	kfree(prop->name);
	kfree(prop->value);
	kfree(prop);
}

static struct platform_device *add_device(const char *name, struct device_node *np)
{
	struct platform_device *pdev;
	int ret;

	pdev = platform_device_alloc(name, PLATFORM_DEVID_NONE);
	if (!pdev)
		return ERR_PTR(-ENOMEM);
	pdev->dev.of_node = of_node_get(np);
	/* These donors are already part of the live tree. Do not claim their
	 * normal firmware linkage as if this were the original hardware device.
	 */
	pdev->dev.of_node_reused = true;
	ret = platform_device_add(pdev);
	if (ret) {
		platform_device_put(pdev);
		return ERR_PTR(ret);
	}
	return pdev;
}

static void remove_devices(void)
{
	if (wonder_pdev) {
		platform_device_unregister(wonder_pdev);
		wonder_pdev = NULL;
	}
	if (provider_pdev) {
		platform_device_unregister(provider_pdev);
		provider_pdev = NULL;
	}
	if (link_prop) {
		int ret = of_remove_property(wonder_np, link_prop);
		pr_info("mtk_wonder_bind: remove property rc=%d\n", ret);
		/* of_remove_property retains it; never free published storage. */
		link_prop = NULL;
	}
	of_node_put(wonder_np);
	of_node_put(provider_np);
	wonder_np = provider_np = NULL;
}

static int validate_donor(struct device_node *np)
{
	struct platform_device *existing;

	if (of_get_child_count(np) || of_find_property(np, "compatible", NULL) ||
	    of_find_property(np, "reg", NULL) || of_find_property(np, "status", NULL))
		return -EINVAL;
	existing = of_find_device_by_node(np);
	if (existing) {
		put_device(&existing->dev);
		return -EBUSY;
	}
	return 0;
}

static int __init bind_init(void)
{
	struct property *prop;
	int ret;

	if (!provider_node || !wonder_node)
		return -EINVAL;
	provider_np = of_find_node_by_path(provider_node);
	wonder_np = of_find_node_by_path(wonder_node);
	if (!provider_np || !wonder_np || provider_np == wonder_np) {
		ret = -EINVAL;
		goto fail;
	}
	ret = validate_donor(provider_np);
	if (ret)
		goto fail;
	ret = validate_donor(wonder_np);
	if (ret)
		goto fail;
	if (!provider_np->phandle ||
	    of_find_property(wonder_np, "wondertap-provider", NULL)) {
		ret = -EINVAL;
		goto fail;
	}
	pr_info("mtk_wonder_bind: donors validated; phandle=%x activate=%d\n",
		provider_np->phandle, activate);
	if (!activate)
		return 0;

	/* Both stock drivers must already be registered. Refuse to replace
	 * devices, unload modules, enable radios, or launch userspace here.
	 */
	prop = alloc_link(provider_np->phandle);
	if (!prop) {
		ret = -ENOMEM;
		goto fail;
	}
	ret = of_add_property(wonder_np, prop);
	if (ret) {
		free_unpublished_link(prop);
		goto fail;
	}
	link_prop = prop;
	provider_pdev = add_device("vendor_wonder_dev", provider_np);
	if (IS_ERR(provider_pdev)) {
		ret = PTR_ERR(provider_pdev);
		provider_pdev = NULL;
		goto fail;
	}
	if (!provider_pdev->dev.driver) {
		ret = -ENODEV;
		goto fail;
	}
	wonder_pdev = add_device("wonder", wonder_np);
	if (IS_ERR(wonder_pdev)) {
		ret = PTR_ERR(wonder_pdev);
		wonder_pdev = NULL;
		goto fail;
	}
	if (!wonder_pdev->dev.driver || !platform_get_drvdata(provider_pdev)) {
		ret = -ENODEV;
		goto fail;
	}
	pr_info("mtk_wonder_bind: stock provider and wonder master bound\n");
	return 0;
fail:
	pr_err("mtk_wonder_bind: refused/failed rc=%d\n", ret);
	remove_devices();
	return ret;
}

static void __exit bind_exit(void)
{
	remove_devices();
	pr_info("mtk_wonder_bind: detached\n");
}

module_init(bind_init);
module_exit(bind_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("PME110 stock MTK Wonder runtime binding experiment");
