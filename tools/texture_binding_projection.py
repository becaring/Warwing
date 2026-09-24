"""Transfer SoH's certified texture bindings and delayed import flushes.

Donor: current SoH360 gfx_pc.cpp:261,634-719,2276-2281,2348-2351.
BattleShip retains all imports, complete keys, content verification, LRU work,
texture decoders, framebuffer UV handling, and mask/replacement behavior.
The certificate is separate from RenderingState's resource-node pointers.
"""
from profile_projections import once


def header(text):
    text='#include "fast3d/texture_bindings.h"\n'+text
    text=once(text,'    void TextureCacheClear();',
        '    void XboxInvalidateTextureBindings();\n    void TextureCacheClear();')
    return once(text,'    GfxTextureCache mTextureCache{};',
        '    GfxTextureCache mTextureCache{};\n    Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES> mXboxTextureBindings;')


def transform(text):
    text=once(text,'Interpreter::Interpreter() {',
        'Interpreter::Interpreter() {\n    XboxInvalidateTextureBindings();')
    text=once(text,'void Interpreter::SpReset() {',
        'void Interpreter::SpReset() {\n    XboxInvalidateTextureBindings();')
    text=once(text,'    mRapi = rapi;',
        '    mRapi = rapi;\n    XboxInvalidateTextureBindings();')
    text=once(text,'GfxRenderingAPI* Interpreter::GetCurrentRenderingAPI() {',
        '''GfxRenderingAPI* Interpreter::GetCurrentRenderingAPI() {
    // External API users can select/upload/delete textures. Finish queued
    // users before exposing mutable backend state, then require certification.
    Flush();
    XboxInvalidateTextureBindings();''')
    text=once(text,'void Interpreter::TextureCacheClear() {','''void Interpreter::XboxInvalidateTextureBindings() {
    mXboxTextureBindings.Invalidate();
}

void Interpreter::TextureCacheClear() {
    Flush();
    XboxInvalidateTextureBindings();''')
    text=once(text,'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {',
        '''void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {
    Flush();
    XboxInvalidateTextureBindings();''')
    text=once(text,'    const uint8_t* end = base + size;\n    for (auto it = mTextureCache.map.begin();',
        '''    Flush();
    XboxInvalidateTextureBindings();
    const uint8_t* end = base + size;
    for (auto it = mTextureCache.map.begin();''')
    text=once(text,'    TextureCacheMap::iterator it = mTextureCache.map.find(key);\n    TextureCacheNode** n',
        '    TextureCacheNode** n')
    anchor='''    if (it != mTextureCache.map.end()) {
        if (verify && it->second.content_hash != content_hash) {'''
    text=once(text,anchor,'''    // Content verification above is mandatory even on a direct binding hit:
    // Smash reuses raw CPU addresses for different texture contents.
    TextureCacheNode* bound = mXboxTextureBindings.Bound<TextureCacheNode>(i);
    if (bound && bound->first == key && (!verify || bound->second.content_hash == content_hash)) {
        const Shipyard::Fast3D::TextureSamplerState sampler(bound->second.linear_filter,
                                                             bound->second.cms,bound->second.cmt);
        if (mXboxTextureBindings.NeedsSelect(i,bound,bound->second.texture_id,sampler)) {
            Flush();
            mRapi->SelectTexture(i,bound->second.texture_id);
            mXboxTextureBindings.Selected(i,bound,bound->second.texture_id,sampler);
        }
        *n = bound;
        mTextureCache.lru.splice(mTextureCache.lru.end(), mTextureCache.lru, bound->second.lru_location);
        return true;
    }
    TextureCacheMap::iterator it = mTextureCache.map.find(key);
    if (it != mTextureCache.map.end()) {
        if (verify && it->second.content_hash != content_hash) {
            Flush();
            XboxInvalidateTextureBindings();''')
    text=once(text,'            mRapi->SelectTexture(i, it->second.texture_id);',
        '''            const Shipyard::Fast3D::TextureSamplerState sampler(it->second.linear_filter,
                                                                 it->second.cms,it->second.cmt);
            if (mXboxTextureBindings.NeedsSelect(i,&*it,it->second.texture_id,sampler)) {
                Flush();
                mRapi->SelectTexture(i, it->second.texture_id);
                mXboxTextureBindings.Selected(i,&*it,it->second.texture_id,sampler);
            }''')
    text=once(text,'    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {',
        '''    // A miss may evict any aliased node and recycle a GPU ID. Finish
    // existing users before any erase, select, sampler change or upload.
    Flush();
    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {
        XboxInvalidateTextureBindings();''')
    text=once(text,'    mRapi->SelectTexture(i, texture_id);\n    mRapi->SetSamplerParameters',
        '    mRapi->SelectTexture(i, texture_id);\n'
        '    mXboxTextureBindings.Selected(i,node,texture_id,Shipyard::Fast3D::TextureSamplerState());\n'
        '    mRapi->SetSamplerParameters')
    text=once(text,
        '''            bool linear_filter = (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
            if (linear_filter != mRenderingState.mTextures[i]->second.linear_filter ||
                cms != mRenderingState.mTextures[i]->second.cms || cmt != mRenderingState.mTextures[i]->second.cmt) {''',
        '''            bool linear_filter = (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
            const Shipyard::Fast3D::TextureSamplerState desiredSampler(linear_filter,cms,cmt);
            if (linear_filter != mRenderingState.mTextures[i]->second.linear_filter ||
                cms != mRenderingState.mTextures[i]->second.cms || cmt != mRenderingState.mTextures[i]->second.cmt ||
                mXboxTextureBindings.NeedsSampler(i,desiredSampler) ||
                (mRdp->loaded_texture[i].blended &&
                 mXboxTextureBindings.NeedsSampler(SHADER_FIRST_REPLACEMENT_TEXTURE+i,desiredSampler))) {''')
    text=once(text,
        '                    mRapi->SetSamplerParameters(SHADER_FIRST_REPLACEMENT_TEXTURE + i, linear_filter, cms, cmt);',
        '                    mRapi->SetSamplerParameters(SHADER_FIRST_REPLACEMENT_TEXTURE + i, linear_filter, cms, cmt);\n'
        '                    mXboxTextureBindings.SamplerChanged(SHADER_FIRST_REPLACEMENT_TEXTURE+i,desiredSampler);')
    text=once(text,
        '                mRapi->SetSamplerParameters(i, linear_filter, cms, cmt);',
        '                mRapi->SetSamplerParameters(i, linear_filter, cms, cmt);\n'
        '                mXboxTextureBindings.SamplerChanged(i,desiredSampler);')
    text=once(text,'''            if (mRdp->textures_changed[i]) {
                Flush();
                ImportTexture(i, tile, false);''',
        '''            if (mRdp->textures_changed[i]) {
                // Lookup flushes before a real binding change or upload.
                ImportTexture(i, tile, false);''')
    text=once(text,'                mRapi->SelectTextureFb(it->second.fbId);',
        '''                // This API selects backend slot zero, even when the
                // source import tracks another tile. Invalidate all six.
                XboxInvalidateTextureBindings();
                mRapi->SelectTextureFb(it->second.fbId);''')
    text=once(text,'    gfx->mRapi->SelectTextureFb((uint32_t)cmd->words.w1);',
        '    gfx->XboxInvalidateTextureBindings();\n    gfx->mRapi->SelectTextureFb((uint32_t)cmd->words.w1);')
    text=once(text,'''    if (prg == NULL) {
        comb->prg[tm] = prg =''',
        '''    if (prg == NULL) {
        // Creation immediately changes the native program. The former eager
        // import flush no longer guarantees that the queued batch is empty.
        Flush();
        comb->prg[tm] = prg =''')
    return text


def gui(text):
    """Apply after the owned native body selection in prepare_gui_xdk.py."""
    return once(text,'void Gui::ImGuiRenderDrawData(ImDrawData* data) {',
        '''void Gui::ImGuiRenderDrawData(ImDrawData* data) {
    if (auto interpreter = mInterpreter.lock()) {
        interpreter->Flush();
        interpreter->XboxInvalidateTextureBindings();
    }''')
