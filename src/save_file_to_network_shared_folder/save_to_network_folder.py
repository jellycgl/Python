from smb.SMBConnection import SMBConnection

if __name__ == "__main__":
    # find out the machine name by right-clicking on the "My Computer" and selecting "Properties".
    server_ip = "192.168.32.95"
    username = "xxxxxx"
    password = "xxxxxxx"
    my_name = "xxxxxxx"
    remote_name = "xxxxxxx"
    local_file_name = "1.txt"
    shared_directory = "Share Folder"
    shared_sub_directory = 'config'
    shared_file_name = "1.txt"
    conn = SMBConnection(username, password, my_name, remote_name, is_direct_tcp = True)
    result = conn.connect(server_ip, 445)

    is_sub_exist = False
    sharelist = conn.listPath(shared_directory,"/")
    for i in sharelist:
        if i.filename == shared_sub_directory:
            is_sub_exist = True
    if not is_sub_exist:
        conn.createDirectory(shared_directory, shared_sub_directory)
    
    local_file = open(local_file_name,"rb")
    try:
        conn.storeFile(shared_directory, shared_sub_directory + '\\' + shared_file_name, local_file)
    except Exception as e:
        print(e)
    finally:
        local_file.close() 

    conn.close()