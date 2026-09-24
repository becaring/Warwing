#include <zip.h>
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <stdexcept>
#ifdef ADAPTED_LIBZIP
#include "filesystem/filesystem.h"
#endif

static void require(bool value, const char *what) { if (!value) throw std::runtime_error(what); }
static std::string read(zip_t *archive, const char *name, const char *password = NULL) {
    zip_file_t *file = password ? zip_fopen_encrypted(archive, name, 0, password) : zip_fopen(archive, name, 0);
    require(file != NULL, "open entry");
    std::string out; char bytes[173]; zip_int64_t count;
    while ((count=zip_fread(file,bytes,sizeof(bytes))) > 0) out.append(bytes,static_cast<size_t>(count));
    require(count == 0, "read entry including CRC");
    require(zip_fclose(file) == 0, "close entry");
    return out;
}
static void add(zip_t *archive, const char *name, const std::string& bytes) {
    void *copy=malloc(bytes.size());require(copy!=NULL,"entry copy");memcpy(copy,bytes.data(),bytes.size());
    zip_source_t *source=zip_source_buffer(archive,copy,bytes.size(),1);
    if(!source) free(copy);
    require(source != NULL, "source buffer");
    const zip_int64_t index=zip_file_add(archive,name,source,ZIP_FL_OVERWRITE|ZIP_FL_ENC_UTF_8);
    if(index < 0) zip_source_free(source);
    require(index >= 0, "add entry");
    require(zip_file_set_mtime(archive,index,1700000000,0)==0,"fixed mtime");
}
int main(int argc,char **argv) {
    try {
        require(argc==3,"arguments");
        require(SetCurrentDirectoryA(argv[1])!=0,"cwd");
#ifdef ADAPTED_LIBZIP
        int uninitialized=0;
        require(zip_open("input.zip",ZIP_RDONLY,&uninitialized)==NULL && uninitialized==ZIP_ER_OPEN,"relative archive requires initialized logical cwd");
        xbox_compat::filesystem::InitWorkingDirectory(argv[1]);
#endif
        int error=0;
        zip_t *archive=zip_open("input.zip",ZIP_RDONLY,&error);
        require(archive!=NULL,"open fixture");
        require(zip_get_num_entries(archive,0)==6,"entry count");
        const std::string stored=read(archive,"stored.bin"), deflated=read(archive,"deflated.bin");
        require(stored==deflated && stored.size()==700000,"stored/deflated parity");
        require(read(archive,"empty").empty(),"empty entry");
        require(read(archive,"zip64-local")=="ZIP64 local header","ZIP64 local header");
        require(read(archive,"folder/caf\xc3\xa9.txt")=="entry names keep UTF-8","utf8 entry");
        zip_file_t *seek=zip_fopen(archive,"stored.bin",0);require(seek!=NULL,"seek entry");
        require(zip_fseek(seek,543210,SEEK_SET)==0 && zip_ftell(seek)==543210,"entry seek/tell");
        char part[99];require(zip_fread(seek,part,sizeof(part))==sizeof(part),"seek read");
        require(memcmp(part,stored.data()+543210,sizeof(part))==0,"seek data");
        require(zip_fclose(seek)==0,"seek close");
        require(zip_delete(archive,0)<0 && zip_error_code_zip(zip_get_error(archive))==ZIP_ER_RDONLY,"readonly error");
        zip_discard(archive);
        zip_error_t source_error;zip_error_init(&source_error);
        zip_source_t *range=zip_source_file_create("input.zip",4,32,&source_error);
        require(range!=NULL && zip_source_open(range)==0,"bounded native file source");
        require(zip_source_read(range,part,99)==32 && zip_source_tell(range)==32,"source range length/tell");
        require(zip_source_seek(range,3,SEEK_SET)==0 && zip_source_tell(range)==3,"source seek");
        require(zip_source_read(range,part,99)==29,"source range seek read");
        require(zip_source_close(range)==0,"source close");zip_source_free(range);zip_error_fini(&source_error);
        archive=zip_open("output.zip",ZIP_CREATE|ZIP_TRUNCATE,&error);require(archive!=NULL,"create zip");
        add(archive,"data",stored);add(archive,"remove",std::string("bye"));
        require(zip_set_file_compression(archive,0,ZIP_CM_DEFLATE,9)==0,"deflate method");
        require(zip_set_archive_comment(archive,"actual-libzip",13)==0,"comment");
        require(zip_close(archive)==0,"commit create");
        archive=zip_open("output.zip",0,&error);require(archive!=NULL,"reopen");
        require(read(archive,"data")==stored,"created data");
        require(zip_file_rename(archive,0,"renamed",0)==0 && zip_delete(archive,1)==0,"rename/delete");
        const std::string replacement="replacement remains alive through zip_close";add(archive,"renamed",replacement);
        require(zip_close(archive)==0,"commit replacement");
        archive=zip_open("output.zip",ZIP_RDONLY,&error);require(archive && read(archive,"renamed")==replacement,"replacement data");
        require(zip_get_num_entries(archive,0)==1,"deleted count");zip_discard(archive);
        archive=zip_open("corrupt.zip",ZIP_RDONLY,&error);require(archive!=NULL,"open corrupt fixture");
        zip_file_t *bad=zip_fopen(archive,"data",0);require(bad!=NULL,"open corrupt entry");
        char temp[128];zip_int64_t got;do{got=zip_fread(bad,temp,sizeof(temp));}while(got>0);
        require(got<0 && zip_error_code_zip(zip_file_get_error(bad))==ZIP_ER_CRC,"CRC failure");
        zip_fclose(bad);zip_discard(archive);
        archive=zip_open("unsupported.zip",ZIP_RDONLY,&error);require(archive!=NULL,"open unsupported fixture");
        require(zip_fopen(archive,"data",0)==NULL && zip_error_code_zip(zip_get_error(archive))==ZIP_ER_COMPNOTSUPP,"unsupported compression");zip_discard(archive);
        require(zip_open("truncated.zip",ZIP_RDONLY,&error)==NULL && error!=0,"truncated archive");
        require(zip_open("missing.zip",ZIP_RDONLY,&error)==NULL && error==ZIP_ER_NOENT,"missing path");
        HANDLE held=CreateFileA("blocked.zip",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
        require(held!=INVALID_HANDLE_VALUE,"lock destination");
        archive=zip_open("blocked.zip",0,&error);require(archive!=NULL,"open locked destination");add(archive,"added",replacement);
        require(zip_close(archive)<0 && zip_error_code_zip(zip_get_error(archive))==ZIP_ER_RENAME,"replacement sharing failure");
#ifdef ADAPTED_LIBZIP
        HANDLE new_owner=CreateEvent(NULL,TRUE,FALSE,NULL);require(new_owner!=NULL,"new handle after failed commit");
#endif
        zip_discard(archive);CloseHandle(held);
#ifdef ADAPTED_LIBZIP
        require(SetEvent(new_owner)!=0 && WaitForSingleObject(new_owner,0)==WAIT_OBJECT_0,"rollback did not close a subsequently reused handle");CloseHandle(new_owner);
#endif
        archive=zip_open("blocked.zip",ZIP_RDONLY,&error);require(archive && read(archive,"data")=="original","failed write preserved original");zip_discard(archive);
        archive=zip_open("encrypted.zip",ZIP_CREATE|ZIP_TRUNCATE,&error);require(archive!=NULL,"encrypted create");add(archive,"secret",replacement);
        require(zip_file_set_encryption(archive,0,ZIP_EM_TRAD_PKWARE,"password")==0,"traditional encryption");require(zip_close(archive)==0,"encrypted commit");
        archive=zip_open("encrypted.zip",ZIP_RDONLY,&error);require(archive!=NULL && read(archive,"secret","password")==replacement,"encrypted read");
        bad=zip_fopen_encrypted(archive,"secret",0,"wrong");
        if(bad) { do{got=zip_fread(bad,temp,sizeof(temp));}while(got>0);require(got<0,"bad password read");zip_fclose(bad); }
        zip_discard(archive);
#ifdef ADAPTED_LIBZIP
        zip_error_t detail;zip_error_init(&detail);
        require(zip_source_file_create("caf\xc3\xa9.zip",0,-1,&detail)==NULL && zip_error_code_zip(&detail)==ZIP_ER_INVAL,"native filename encoding rejected");
        require(zip_source_win32w_create(L"input.zip",0,-1,&detail)==NULL && zip_error_code_zip(&detail)==ZIP_ER_OPNOTSUPP,"wide unsupported");
        held=CreateFileA("input.zip",GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);require(held!=INVALID_HANDLE_VALUE,"raw handle");
        require(zip_source_win32handle_create(held,0,-1,&detail)==NULL && zip_error_code_zip(&detail)==ZIP_ER_OPNOTSUPP,"opaque handle unsupported");
        require(CloseHandle(held)!=0,"unsupported source retained caller handle");zip_error_fini(&detail);
#endif
        FILE *result=NULL;require(fopen_s(&result,argv[2],"wb")==0,"result file");
        require(fwrite(stored.data(),1,stored.size(),result)==stored.size(),"result data");fclose(result);
        puts("PASS real stored/deflated/UTF-8 entries, seek, writes, encryption, failures and lifetime");return 0;
    } catch(const std::exception& error) {fprintf(stderr,"FAIL %s\n",error.what());return 1;}
}
