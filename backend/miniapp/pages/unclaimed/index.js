const API = getApp().globalData.API

Page({
  data: { packages: [], loading: true },

  async onLoad()  { await this.fetchUnclaimed() },
  onShow()        { this.fetchUnclaimed() },

  async fetchUnclaimed() {
    this.setData({ loading: true })
    try {
      const res = await dd.httpRequest({ url: `${API}/unclaimed`, method: "GET" })
      this.setData({ packages: res.data, loading: false })
    } catch (e) {
      dd.alert({ title: "加载失败", content: e.message || "请检查网络" })
      this.setData({ loading: false })
    }
  },

  async onClaim(e) {
    const slot = e.currentTarget.dataset.slot
    const { data: userId } = dd.getStorageSync({ key: "userId" })

    dd.confirm({
      title: "确认认领",
      content: `确认这是你的包裹？\n格子编号：${slot} 号格`,
      confirmButtonText: "是的，认领",
      cancelButtonText: "取消",
      success: async (res) => {
        if (!res.confirm) return
        try {
          await dd.httpRequest({
            url: `${API}/unclaimed/${slot}/claim`,
            method: "POST",
            data: JSON.stringify({ employee_id: userId }),
            headers: { "Content-Type": "application/json" }
          })
          dd.alert({
            title: "认领成功",
            content: `${slot} 号格已归入你的名下，请到快递间取件`
          })
          await this.fetchUnclaimed()
        } catch (e) {
          dd.alert({ title: "操作失败", content: e.message || "请重试" })
        }
      }
    })
  }
})
