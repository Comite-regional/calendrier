// ===== dates_cles_filter.js =====
// N'affiche que les dates clés en cours ou à venir

function filterFutureKeyDates(items) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return items.filter(item => {
    const endRaw = item.end || item.date_fin || item.dateFin;
    if (!endRaw) return true;
    const endDate = new Date(endRaw);
    endDate.setHours(23, 59, 59, 999);
    return endDate >= today;
  });
}
