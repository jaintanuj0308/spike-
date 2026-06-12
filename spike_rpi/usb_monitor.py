# usb_monitor.py - USB insert/remove detection using pyudev and asyncio reader
import asyncio
import logging
import sys
import config
import spike_logic
from spike_state import SpikeState

logger = logging.getLogger("usb_monitor")

class USBMonitor:
    def __init__(self, spike_state: SpikeState):
        self.spike_state = spike_state
        self.active_devices = {}  # Maps physical device_path -> player_id
        self.monitor = None
        self.has_udev = False
        self._initialized = False  # Guard: ignore events until startup scan completes
        
        if config.ENABLE_USB_MONITOR:
            try:
                
                
                import pyudev
                self.context = pyudev.Context()
                self.monitor = pyudev.Monitor.from_netlink(self.context)
                # Filter for block storage devices (USBs)
                self.monitor.filter_by(subsystem='block')
                self.monitor.start()
                self.has_udev = True
                logger.info("pyudev monitor initialized successfully.")
            except ImportError:
                logger.warning("pyudev is not installed. Running USB monitor in Mock Mode.")
            except Exception as e:
                logger.warning(f"Failed to initialize pyudev ({e}). Running USB monitor in Mock Mode.")
        else:
            logger.info("USB Monitor disabled via config. Running in Mock Mode.")

    def start(self):
        """Starts monitoring USB events. Registers callback with asyncio on Linux.
        Falls back to a polling loop when pyudev is unavailable (e.g., on systems without udev)."""
        if not self.has_udev or not self.monitor:
            logger.info("USB Monitor started in Mock Mode (no physical USB tracking). Starting fallback poll loop.")
            # Start async poll loop for USB detection
            asyncio.create_task(self.poll_loop())
            return

        try:
            loop = asyncio.get_running_loop()
            # Register the monitor's file descriptor as a reader in the event loop
            loop.add_reader(self.monitor.fileno(), self._handle_udev_event)
            logger.info("USB Monitor reader added to asyncio event loop successfully.")
            # Schedule startup initialization: drain any queued events and set initialized flag
            asyncio.create_task(self._startup_init())
        except Exception as e:
            logger.error(f"Failed to register udev reader with event loop: {e}")

    async def _startup_init(self):
        """Drain any queued udev events from before startup, then mark as initialized."""
        # Brief delay to let any boot-time udev events arrive and get drained
        await asyncio.sleep(2)
        # Drain any queued events that arrived during startup (discard them)
        if self.monitor:
            event = self.monitor.poll(timeout=0)
            drained = 0
            while event is not None:
                drained += 1
                event = self.monitor.poll(timeout=0)
            if drained:
                logger.info(f"Drained {drained} startup udev event(s) (ignored).")
        self._initialized = True
        logger.info("USB Monitor initialized — now reacting to USB events.")

    def _handle_udev_event(self):
        """Callback from asyncio reader when the monitor fileno is readable."""
        if not self.monitor:
            return
        
        if not self._initialized:
            # Drain events silently during startup
            event = self.monitor.poll(timeout=0)
            while event is not None:
                logger.debug(f"Ignoring pre-init udev event: {event.action} on {event.device_path}")
                event = self.monitor.poll(timeout=0)
            return
            
        # Poll non-blocking to retrieve all queued udev events
        event = self.monitor.poll(timeout=0)
        while event is not None:
            # Spawn event processing task asynchronously so we don't block
            asyncio.create_task(self._process_event(event))
            event = self.monitor.poll(timeout=0)

    async def _process_event(self, event):
        """Processes a single udev device add/remove event."""
        try:
            action = event.action
            devtype = event.get('DEVTYPE')

            # Only process the main disk block device to avoid duplicate events from partition tables
            if devtype != 'disk':
                return

            logger.debug(f"udev event: {action} on {event.device_path} (devtype: {devtype})")

            if action == 'add':
                # Any USB insertion is treated as an attacker key (default ID)
                player_id = 'A1'
                logger.info(f"USB inserted (any device); defaulting to attacker ID '{player_id}'.")
                # Track device path for proper removal handling
                self.active_devices[event.device_path] = player_id
                logger.info(f"USB Added: {event.device_path} mapped to Player/Team: {player_id}")

                # Retrieve current state
                state_data = await self.spike_state.get_state()

                if state_data.state == "idle":
                    logger.info(f"USB key detected! Starting planting for player: {player_id}")
                    await spike_logic.start_plant(self.spike_state, player_id)
                elif state_data.state == "planted":
                    logger.info(f"USB key detected! Starting defusing for player: {player_id}")
                    await spike_logic.start_defuse(self.spike_state, player_id, skip_role_check=True)
                elif state_data.state == "defusing":
                    # USB re-inserted while defusing → cancel defuse, resume spike timer
                    logger.info(f"USB re-inserted during DEFUSING; cancelling defuse, resuming spike timer.")
                    await spike_logic.cancel_defuse(self.spike_state)

            elif action == 'remove':
                player_id = self.active_devices.pop(event.device_path, None)
                if player_id:
                    logger.info(f"USB Removed: {event.device_path} was Player/Team: {player_id}")
                    # Check current state to decide next action
                    current_state = await self.spike_state.get_state()
                    if current_state.state == "planted":
                        # USB removal after spike is planted should start defusing
                        # skip_role_check=True because the attacker's USB triggers the defuse
                        logger.info(f"USB removal detected in PLANTED state; starting defusing for player: {player_id}")
                        await spike_logic.start_defuse(self.spike_state, player_id, skip_role_check=True)
                    elif current_state.state == "defusing":
                        # Already defusing (duplicate event from same USB, e.g. disk + partition)
                        logger.debug(f"Already in DEFUSING state, ignoring duplicate remove event for {event.device_path}")
                    else:
                        await spike_logic.on_player_killed(self.spike_state, player_id)
        except Exception as e:
            logger.error(f"Error processing udev event: {e}", exc_info=True)

    def _identify_device(self, event) -> str:
        """Attempts to identify the player ID associated with this USB event properties."""
        serial_short = event.get('ID_SERIAL_SHORT')
        serial_long = event.get('ID_SERIAL')
        vendor_id = event.get('ID_VENDOR_ID')
        model_id = event.get('ID_MODEL_ID')

        # 1. Match by short serial
        if serial_short and serial_short in config.USB_DEVICE_MAP:
            return config.USB_DEVICE_MAP[serial_short]

        # 2. Match by long serial
        if serial_long and serial_long in config.USB_DEVICE_MAP:
            return config.USB_DEVICE_MAP[serial_long]

        # 3. Match by vendor_id:model_id
        if vendor_id and model_id:
            vm_key = f"{vendor_id}:{model_id}"
            if vm_key in config.USB_DEVICE_MAP:
                return config.USB_DEVICE_MAP[vm_key]

        # Log device characteristics for easy operator config setup
        print("\n==============================================")
        print("      UNRECOGNIZED USB DEVICE DETECTED        ")
        print("==============================================")
        print(f"  Device Path : {event.device_path}")
        print(f"  Short Serial: {serial_short or 'None'}")
        print(f"  Long Serial : {serial_long or 'None'}")
        print(f"  Vendor ID   : {vendor_id or 'None'}")
        print(f"  Model ID    : {model_id or 'None'}")
        print(f"  Config Key  : {vendor_id}:{model_id}" if vendor_id and model_id else "  Config Key  : N/A")
        print("==============================================")
        print("To assign this USB, copy one of the serials or")
        print("the Config Key to config.py USB_DEVICE_MAP.")
        print("==============================================\n")
        sys.stdout.flush()

        return None

    async def poll_loop(self):
        """Fallback polling loop when udev monitor is unavailable.
        Scans /dev/disk/by-id for block devices every 2 seconds.
        """
        from pathlib import Path
        # Initial baseline scan: treat all currently-connected devices as already known
        # so they don't trigger start_plant on first iteration
        base_path = Path('/dev/disk/by-id')
        if base_path.is_dir():
            known = {p.resolve() for p in base_path.iterdir() if p.is_symlink() and "-part" not in p.name}
        else:
            known = set()
        logger.info(f"[POLL] Initial baseline: {len(known)} existing device(s) detected and ignored.")
        while True:
            try:
                base_path = Path('/dev/disk/by-id')
                if base_path.is_dir():
                    current = {p.resolve() for p in base_path.iterdir() if p.is_symlink() and "-part" not in p.name}
                else:
                    current = set()
                added = current - known
                removed = known - current
                for dev in added:
                    player_id = 'A1'
                    logger.info(f"[POLL] Detected new USB {dev}, treating as '{player_id}'")
                    self.active_devices[str(dev)] = player_id
                    state_data = await self.spike_state.get_state()
                    if state_data.state == 'idle':
                        await spike_logic.start_plant(self.spike_state, player_id)
                    elif state_data.state == 'planted':
                        await spike_logic.start_defuse(self.spike_state, player_id, skip_role_check=True)
                    elif state_data.state == 'defusing':
                        logger.info(f"[POLL] USB re-inserted during DEFUSING; cancelling defuse.")
                        await spike_logic.cancel_defuse(self.spike_state)
                for dev in removed:
                    pid = self.active_devices.pop(str(dev), None)
                    if pid:
                        logger.info(f"[POLL] USB removed {dev}, player: {pid}")
                        state_data = await self.spike_state.get_state()
                        if state_data.state == 'planted':
                            logger.info(f"[POLL] USB removal in PLANTED state; starting defuse for {pid}")
                            await spike_logic.start_defuse(self.spike_state, pid, skip_role_check=True)
                        elif state_data.state == 'defusing':
                            logger.debug(f"[POLL] Already in DEFUSING state, ignoring duplicate remove.")
                        else:
                            await spike_logic.on_player_killed(self.spike_state, pid)
                known = current
            except Exception as e:
                logger.error(f"[POLL] Error in USB poll loop: {e}", exc_info=True)
            await asyncio.sleep(2)


    def mock_trigger_insert(self, player_id: str, device_path: str = "/dev/mock_usb"):
        """Simulates insertion of a USB drive for testing."""
        logger.info(f"[MOCK USB] Inserting mock USB for {player_id} at {device_path}")
        
        # Setup event logic manually
        self.active_devices[device_path] = player_id
        asyncio.create_task(self._simulate_insert(player_id))

    async def _simulate_insert(self, player_id: str):
        state_data = await self.spike_state.get_state()
        if state_data.state == "idle":
            await spike_logic.start_plant(self.spike_state, player_id)
        elif state_data.state == "planted":
            await spike_logic.start_defuse(self.spike_state, player_id, skip_role_check=True)
        elif state_data.state == "defusing":
            logger.info(f"[MOCK USB] Re-inserted during DEFUSING; cancelling defuse.")
            await spike_logic.cancel_defuse(self.spike_state)

    def mock_trigger_remove(self, player_id: str):
        """Simulates removal of a USB drive for testing."""
        logger.info(f"[MOCK USB] Removing mock USB for {player_id}")
        
        # Find paths matching player_id
        paths_to_remove = [path for path, pid in self.active_devices.items() if pid == player_id]
        for path in paths_to_remove:
            self.active_devices.pop(path, None)
            
        asyncio.create_task(self._simulate_remove(player_id))

    async def _simulate_remove(self, player_id: str):
        """Handles mock USB removal with proper state checking."""
        state_data = await self.spike_state.get_state()
        if state_data.state == "planted":
            logger.info(f"[MOCK USB] Removal in PLANTED state; starting defuse for {player_id}")
            await spike_logic.start_defuse(self.spike_state, player_id, skip_role_check=True)
        elif state_data.state == "defusing":
            logger.debug(f"[MOCK USB] Already in DEFUSING state, ignoring duplicate remove.")
        else:
            await spike_logic.on_player_killed(self.spike_state, player_id)
