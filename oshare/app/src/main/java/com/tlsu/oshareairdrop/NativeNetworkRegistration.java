package com.tlsu.oshareairdrop;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.IpPrefix;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.RouteInfo;
import android.os.HandlerThread;
import android.os.Looper;
import android.util.Log;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;

/** Register the explicit native lease using the stock 27391 network-agent contract. */
final class NativeNetworkRegistration {
    private static Object agent;
    private static HandlerThread thread;
    private static int interfaceIndex = -1;
    private static long registeredAt;
    private static final String TAG = "OShareAirDrop";

    static synchronized void reconcile(NetworkInterface iface) throws Exception {
        Context context = HostContext.get();
        ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
        for (Network network : manager.getAllNetworks()) {
            LinkProperties properties = manager.getLinkProperties(network);
            if (properties != null && "mosey0".equals(properties.getInterfaceName())) {
                if (agent != null && interfaceIndex != iface.getIndex()) release();
                return;
            }
        }
        // Registration is asynchronous. Do not create duplicate agents while it settles.
        if (agent != null && interfaceIndex == iface.getIndex()
                && android.os.SystemClock.elapsedRealtime() - registeredAt < 15000) return;
        release();
        ArrayList<LinkAddress> addresses = new ArrayList<>();
        for (InterfaceAddress address : iface.getInterfaceAddresses())
            addresses.add(LinkAddress.class.getConstructor(InetAddress.class, int.class)
                    .newInstance(address.getAddress(), (int) address.getNetworkPrefixLength()));
        if (addresses.isEmpty()) return;
        LinkProperties properties = new LinkProperties();
        properties.setInterfaceName(iface.getName());
        properties.setLinkAddresses(addresses);
        properties.addRoute(RouteInfo.class.getConstructor(IpPrefix.class, InetAddress.class,
                String.class, int.class).newInstance(new IpPrefix(InetAddress.getByName("fe80::"), 64), null, iface.getName(), 1));
        ClassLoader loader = ProviderHolder.loader();
        Class<?> configClass = Class.forName("android.net.NetworkAgentConfig");
        Class<?> builderClass = Class.forName("android.net.NetworkAgentConfig$Builder");
        Object builder = builderClass.getConstructor().newInstance();
        builderClass.getMethod("setLegacyTypeName", String.class).invoke(builder, "WIFI_AWARE_FACTORY");
        builderClass.getMethod("setLegacyType", int.class).invoke(builder, -1);
        Object config = builderClass.getMethod("build").invoke(builder);
        // Reuse stock capabilities (LOWPAN, NOT_METERED, NOT_VPN), not Internet access.
        Object stockNetwork = loader.loadClass("bog").getConstructor(Context.class).newInstance(context);
        NetworkCapabilities capabilities = (NetworkCapabilities) stockNetwork.getClass().getField("d").get(stockNetwork);
        thread = new HandlerThread("OShareNativeNetwork");
        thread.start();
        try {
            Class<?> providerClass = Class.forName("android.net.NetworkProvider");
            Object provider = providerClass.getConstructor(Context.class, Looper.class, String.class)
                    .newInstance(context, thread.getLooper(), "OShareNativeNetworkProvider");
            agent = loader.loadClass("boh").getConstructor(Context.class, Looper.class,
                    NetworkCapabilities.class, LinkProperties.class, configClass, providerClass)
                    .newInstance(context, thread.getLooper(), capabilities, properties, config, provider);
            Class<?> agentClass = Class.forName("android.net.NetworkAgent");
            Object network = agentClass.getMethod("register").invoke(agent);
            agentClass.getMethod("markConnected").invoke(agent);
            interfaceIndex = iface.getIndex();
            registeredAt = android.os.SystemClock.elapsedRealtime();
            Log.i(TAG, "NATIVE_NETWORK registered interface=" + iface.getName() + " index=" + interfaceIndex + " network=" + network);
        } catch (Exception failure) { release(); throw failure; }
    }

    static synchronized void release() {
        if (agent != null) try {
            Class.forName("android.net.NetworkAgent").getMethod("unregister").invoke(agent);
        } catch (Exception failure) { Log.w(TAG, "NATIVE_NETWORK unregister failed", failure); }
        agent = null;
        if (thread != null) thread.quitSafely();
        thread = null;
        interfaceIndex = -1;
    }
}
