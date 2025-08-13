'use server';

import { getPairedDevices, getRegisteredDevices, revokeDevicePair } from "@/app/account/actions";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Smartphone, Monitor, Trash2, Link as LinkIcon, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { revalidatePath } from 'next/cache';

async function DeviceManagement() {
  try {
    const pairs = await getPairedDevices();
    const allDevices = await getRegisteredDevices();

    const pairedDeviceIds = new Set([
      ...(pairs?.flatMap(p => [p.mobile_device?.id, p.server_device?.id]).filter(Boolean) || []),
    ]);

    const unpairedDevices = allDevices?.filter(d => !pairedDeviceIds.has(d.id)) || [];

    const handleRevoke = async (pairId: string) => {
      'use server';
      try {
        await revokeDevicePair(pairId);
        revalidatePath('/account');
      } catch (error) {
        console.error('Failed to revoke pair:', error);
        // Handle error display if necessary
      }
    };

    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><LinkIcon className="w-5 h-5 mr-2" />Device Management</CardTitle>
          <CardDescription>Manage your connected iOS and macOS devices.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-8">
          <div>
            <h3 className="text-lg font-semibold mb-4">Active Pair</h3>
            {pairs && pairs.length > 0 ? (
              <div className="p-4 border rounded-lg bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700">
                {pairs.map(pair => (
                  <div key={pair.id} className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="flex items-center space-x-2">
                        <Smartphone className="h-6 w-6 text-muted-foreground" />
                        <span className="font-medium">{pair.mobile_device.name}</span>
                      </div>
                      <span className="font-semibold text-muted-foreground">↔</span>
                      <div className="flex items-center space-x-2">
                        <Monitor className="h-6 w-6 text-muted-foreground" />
                        <span className="font-medium">{pair.server_device.name}</span>
                      </div>
                    </div>
                    <form action={async () => { 'use server'; await handleRevoke(pair.id); }}>
                      <Button variant="destructive" size="sm">
                        <Trash2 className="h-4 w-4 mr-2" />
                        Revoke
                      </Button>
                    </form>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-sm text-muted-foreground border-2 border-dashed rounded-lg p-8">
                <p>No devices are currently paired.</p>
                <p className="mt-2">Use the Orion mobile and desktop apps to link devices.</p>
              </div>
            )}
          </div>

          <div className="border-t pt-6">
            <h3 className="text-lg font-semibold mb-4">All Registered Devices</h3>
            {allDevices && allDevices.length > 0 ? (
              <div className="space-y-4">
                {allDevices.map(device => (
                  <div key={device.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-4">
                      {device.type === 'ios' ? <Smartphone className="h-6 w-6 text-muted-foreground" /> : <Monitor className="h-6 w-6 text-muted-foreground" />}
                      <div>
                        <p className="font-medium">{device.name}</p>
                        <p className="text-sm text-muted-foreground">
                          Registered on: {new Date(device.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    {pairedDeviceIds.has(device.id) ? (
                      <Badge variant="default">Paired</Badge>
                    ) : (
                      <Badge variant="secondary">Unpaired</Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No devices have been registered yet.</p>
            )}
          </div>
        </CardContent>
      </Card>
    );
  } catch (error) {
    return (
      <div className="text-destructive-foreground bg-destructive p-4 rounded-md">
        <Info className="h-5 w-5 inline-block mr-2" />
        Failed to load device data. Please try refreshing the page.
      </div>
    );
  }
}

export { DeviceManagement };