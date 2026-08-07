
import sys
from pathlib import Path
sys.path.insert(0,'/Users/jayden/Desktop/Business/AZ-Permit-Radar/.azpr-v10.1-offline-validation/fresh/AZPR-autonomous-execution-primed-draft-v10.1/trusted-installation')
from v9_transaction import AuthorizationTransactionStore,InstallerGlobalLock
i=sys.argv[1]; root=Path('/Users/jayden/Desktop/Business/AZ-Permit-Radar/AZPR/.integration-temp/offline-validation/tmp/pytest-of-jayden/pytest-3/test_f02_f04_twenty_process_sa0')
try:
    with InstallerGlobalLock(root/'global.lock'):
        s=AuthorizationTransactionStore(root/'ledger',str(root/'anchor'),root/'ledger.private.pem','ledger-key-0001','journal-concurrency')
        s.reserve({'authorization_id':'auth-'+i.zfill(8),'nonce':'nonce-'+i.zfill(8),'sequence':1},'a'*64)
    print('SUCCESS')
except BaseException as e: print('FAIL:'+str(e))
