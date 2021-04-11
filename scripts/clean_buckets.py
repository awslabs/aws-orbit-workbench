import boto3
import sys, getopt

 
def delete_buckets(profile, prefix=None):
    print( 'Preparing to delete all buckets with a prefix of '+prefix+' using profile '+profile)
    session = boto3.Session()
    if profile is not None:
        session = boto3.Session(profile_name = profile)
    s3 = session.resource('s3')
    
    buckets_for_delete = []
    for bucket in s3.buckets.all():
        name = bucket.name
        #print(name)
        ## Just to be safe, you MUST have a prefix in order to delete a bucket...we aren't wiping out ALL buckets!!!
        if prefix is not None and name.startswith(prefix):
            buckets_for_delete.append(name)
    if not buckets_for_delete:
        print("No buckets matched that key....exiting")
        exit(0)

    print("Buckets scheduled for deletion - ain't going back now!!   "+ str(buckets_for_delete))
    print('      ')
    print('      ')
    confirm_delete = input("Confirm you want to permanantly delete these buckets!!!!  y or n   ")
    if confirm_delete == 'y' or confirm_delete == 'Y':
        for b in buckets_for_delete:
            print("Permanantly deleting "+b)
            bucket = s3.Bucket(b)
            bucket.object_versions.delete()
            bucket.delete()]
    else:
        print("Deletion Canceled")
        exit(0)


def main(argv):
    profile = 'default'
    prefix = None

    try:
        opts, args = getopt.getopt(argv,'k:p:')
    except getopt.GetoptError as e:
        print('clear_buckets.py -k <prefix key> -p <aws profile>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-k':
            prefix = arg
        elif opt == '-p':
            profile = arg
    if prefix is None:
        print('You must pass in a key, else we delete everything!!!  clear_buckets.py -k <prefix key> -p <aws profile>')
        sys.exit(2)
    delete_buckets(profile, prefix)

if __name__=="__main__":
    main(sys.argv[1:])



